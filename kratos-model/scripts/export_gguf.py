#!/usr/bin/env python3
"""Export fine-tuned model to GGUF for Ollama.

Merges LoRA adapter with base model, quantizes to GGUF Q5_K_M,
and creates an Ollama Modelfile for easy import.

Usage (on Colab after training):
    python scripts/export_gguf.py --lora output/kratos-7b-lora --output output/gguf

Then download the GGUF file and on your local machine:
    ollama create kratos -f output/gguf/Modelfile
"""

from __future__ import annotations

import argparse
from pathlib import Path

from unsloth import FastLanguageModel

MODELFILE_TEMPLATE = '''FROM {gguf_path}

TEMPLATE """<|im_start|>system
{{{{ .System }}}}<|im_end|>
<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
<|im_start|>assistant
"""

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_predict 4096
PARAMETER stop "<|im_end|>"

SYSTEM """You are Kratos, an elite cybersecurity AI agent specialized in penetration testing and CTF challenges.
You operate inside a Kali Linux environment with full access to pentesting tools.
When you need to execute a command or use a tool, wrap it in <tool_call> tags.
Always explain your reasoning before each action.
Methodology: Recon → Enumeration → Vulnerability Analysis → Exploitation → Privilege Escalation → Post-Exploitation"""
'''


def main():
    parser = argparse.ArgumentParser(
        description="Export fine-tuned model to GGUF",
    )
    parser.add_argument(
        "--lora", "-l", default="output/kratos-7b-lora",
        help="Path to LoRA adapter directory",
    )
    parser.add_argument(
        "--output", "-o", default="output/gguf",
        help="Output directory for GGUF file",
    )
    parser.add_argument(
        "--base-model", default="unsloth/Qwen2.5-Coder-7B-Instruct",
        help="Base model (must match training)",
    )
    parser.add_argument(
        "--quant", default="q5_k_m",
        help="Quantization method (q4_k_m, q5_k_m, q8_0, f16)",
    )
    parser.add_argument(
        "--max-seq-len", type=int, default=4096,
        help="Max sequence length",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    lora_dir = base / args.lora
    output_dir = base / args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------
    # 1. Load base model + LoRA adapter
    # ---------------------------------------------------------------
    print(f"Loading base model: {args.base_model}")
    print(f"Loading LoRA from: {lora_dir}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(lora_dir),
        max_seq_length=args.max_seq_len,
        dtype=None,
        load_in_4bit=True,
    )

    # ---------------------------------------------------------------
    # 2. Export to GGUF
    # ---------------------------------------------------------------
    gguf_filename = f"kratos-7b-{args.quant}.gguf"
    gguf_path = output_dir / gguf_filename

    print(f"Exporting to GGUF ({args.quant}): {gguf_path}")
    model.save_pretrained_gguf(
        str(output_dir),
        tokenizer,
        quantization_method=args.quant,
    )

    # Unsloth names the file differently, find it
    gguf_files = list(output_dir.glob("*.gguf"))
    if gguf_files:
        actual_gguf = gguf_files[0]
        if actual_gguf.name != gguf_filename:
            actual_gguf.rename(gguf_path)
        print(f"GGUF saved: {gguf_path}")
    else:
        print("[WARN] No GGUF file found in output!")
        gguf_path = output_dir / "model.gguf"

    # ---------------------------------------------------------------
    # 3. Create Ollama Modelfile
    # ---------------------------------------------------------------
    modelfile_path = output_dir / "Modelfile"
    modelfile_content = MODELFILE_TEMPLATE.format(
        gguf_path=f"./{gguf_path.name}",
    )
    modelfile_path.write_text(modelfile_content)
    print(f"Modelfile saved: {modelfile_path}")

    # ---------------------------------------------------------------
    # 4. Print next steps
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print(f"1. Download the GGUF file: {gguf_path}")
    print(f"   and Modelfile: {modelfile_path}")
    print()
    print("2. On your local machine, place both files in a directory and run:")
    print(f"   ollama create kratos -f Modelfile")
    print()
    print("3. Test it:")
    print("   ollama run kratos")
    print()
    print("4. Update Kratos config:")
    print('   export KRATOS_MODEL="kratos"')
    print("=" * 60)


if __name__ == "__main__":
    main()
