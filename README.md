# GLM-5.2 Function Calling Reproduction

Reproduction package for:
- vllm-project/vllm#47714
- vllm-project/vllm-ascend#11486

## Files

| File | Description |
|------|-------------|
| `req.json` | Request body with 28 tools (sanitized, system prompt simplified) |
| `run_test.py` | Self-contained test script (Python3 stdlib only) |

## Usage

```bash
# 1. Edit run_test.py: replace <your-vllm-endpoint> and <your-api-key>
# 2. Run
python3 run_test.py 20

# 3. Check results
cat results/*/summary.json
```

## Note on req.json

The system prompt in this file is a **simplified version**. The original test used a ~52KB Hermes Agent persona. The bug reproduces with any system prompt that instructs the model to use tools. Feel free to replace with your own system prompt.

## Key parameters

- `chat_template_kwargs.enable_thinking = false` (thinking disabled)
- `stream = false`
- `max_tokens = 65536`
- 28 tools defined

## Sanitized

- API key: replaced with `<your-api-key>`
- Endpoint: replaced with `<your-vllm-endpoint>`
- Enterprise names: removed