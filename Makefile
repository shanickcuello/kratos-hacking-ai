.PHONY: install dev run build-kali clean lint test

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev,tui]"

run:
	kratos

run-target:
	kratos --target $(TARGET)

build-kali:
	docker build -t kratos-kali -f docker/Dockerfile.kali docker/

start-kali:
	docker compose -f docker/docker-compose.yml up -d

stop-kali:
	docker compose -f docker/docker-compose.yml down

lint:
	ruff check src/
	ruff format --check src/

format:
	ruff check --fix src/
	ruff format src/

test:
	pytest tests/

# --- Model pipeline ---

prepare-data:
	python kratos-model/scripts/prepare_dataset.py -i kratos-model/data/raw -o kratos-model/data/processed/train.jsonl

generate-synthetic:
	python kratos-model/scripts/generate_synthetic.py -n 100 -o kratos-model/data/processed/synthetic.jsonl

merge-data:
	cat kratos-model/data/processed/*.jsonl > kratos-model/data/processed/all_train.jsonl
	wc -l kratos-model/data/processed/all_train.jsonl

clean:
	rm -rf dist/ build/ *.egg-info .mypy_cache .pytest_cache .ruff_cache
