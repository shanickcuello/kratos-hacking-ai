#!/usr/bin/env python3
"""Fine-tune Qwen2.5-Coder with QLoRA using Unsloth.

Designed to run on Google Colab Pro (A100 40GB) or locally.
Reads training data from data/processed/*.jsonl files.

Usage (local):
    python scripts/train.py --data data/processed/ --output output/kratos-7b-lora

Usage (Colab):
    See notebooks/train_colab.ipynb which calls this script.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# These imports will be available in the Colab/training environment
# They are NOT needed on your local Mac
from datasets import Dataset
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments


def load_conversations(data_dir: Path) -> list[dict]:
    """Load all JSONL training files into a list of conversations."""
    conversations = []
    for jsonl_file in sorted(data_dir.glob("*.jsonl")):
        print(f"Loading: {jsonl_file.name}")
        with open(jsonl_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                conversations.append(data)
    print(f"Loaded {len(conversations)} total conversations")
    return conversations


def format_chatml(conversation: dict) -> str:
    """Convert a conversation dict to ChatML string for training."""
    parts = []
    for msg in conversation["conversations"]:
        role = msg["role"]
        content = msg["content"]
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    # Add generation prompt at the end
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Kratos model")
    parser.add_argument(
        "--data", "-d", default="data/processed",
        help="Directory with training JSONL files",
    )
    parser.add_argument(
        "--output", "-o", default="output/kratos-7b-lora",
        help="Output directory for LoRA adapter",
    )
    parser.add_argument(
        "--base-model", default="unsloth/Qwen2.5-Coder-7B-Instruct",
        help="Base model from HuggingFace",
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--max-seq-len", type=int, default=4096)
    parser.add_argument("--lora-r", type=int, default=64)
    parser.add_argument("--lora-alpha", type=int, default=128)
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    data_dir = base / args.data
    output_dir = base / args.output

    # ---------------------------------------------------------------
    # 1. Load model with Unsloth (4-bit for training efficiency)
    # ---------------------------------------------------------------
    print(f"Loading base model: {args.base_model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_len,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )

    # ---------------------------------------------------------------
    # 2. Add LoRA adapters
    # ---------------------------------------------------------------
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.1f}%)")

    # ---------------------------------------------------------------
    # 3. Load and format dataset
    # ---------------------------------------------------------------
    raw_data = load_conversations(data_dir)
    formatted = [{"text": format_chatml(c)} for c in raw_data]
    dataset = Dataset.from_list(formatted)
    print(f"Dataset: {len(dataset)} examples")

    # ---------------------------------------------------------------
    # 4. Training
    # ---------------------------------------------------------------
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.01,
        fp16=True,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        optim="adamw_8bit",
        seed=42,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=args.max_seq_len,
        packing=True,  # Pack short sequences for efficiency
    )

    print("Starting training...")
    trainer.train()

    # ---------------------------------------------------------------
    # 5. Save LoRA adapter
    # ---------------------------------------------------------------
    print(f"Saving LoRA adapter to: {output_dir}")
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    print("Done! Run export_gguf.py to convert to GGUF for Ollama.")


if __name__ == "__main__":
    main()
