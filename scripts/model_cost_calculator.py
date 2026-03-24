#!/usr/bin/env python3
"""
Standalone Model Cost Calculator.
Uses hardcoded OpenRouter prices (per 1M tokens) from feedback to compute costs for each model based on given token usage.
No user input required. Models without prices show 'Price not available'.
"""

models = {
    "Claude Sonnet 4.5": {"input": 1281, "output": 268, "total": 1549},
    "Claude Haiku 4.5": {"input": 1281, "output": 259, "total": 1540},
    "Llama 4 Maverick": {"input": 1184, "output": 273, "total": 1457},
    "GPT-4o": {"input": 1173, "output": 218, "total": 1391},
    "Llama 3.3 70B": {"input": 1209, "output": 255, "total": 1464},
    "Gemini 2.5 Flash Lite": {"input": 1190, "output": 221, "total": 1411},
    "Llama 4 Scout": {"input": 1184, "output": 195, "total": 1379},
    "Grok 4.1 Fast": {"input": 1309, "output": 738, "total": 2047},
}

prices = {
    "Claude Sonnet 4.5": {"input": 3.0, "output": 15.0},
    "Claude Haiku 4.5": {"input": 1.0, "output": 5.0},
    "Llama 4 Maverick": {"input": 0.15, "output": 0.60},
    "GPT-4o": {"input": 2.50, "output": 10.0},
    "Llama 4 Scout": {"input": 0.08, "output": 0.30},
    "Grok 4.1 Fast": {"input": 0.20, "output": 0.50},
    "Llama 3.3 70B": {"input": 0.10, "output": 0.32},
    "Gemini 2.5 Flash Lite": {"input": 0.10, "output": 0.40},
    # No prices for Llama 3.3 70B, Gemini 2.5 Flash Lite
}

print("Model Cost Calculator (OpenRouter prices)")
print("Token usage from benchmark.")
print("\nResults:")
for model, tokens in models.items():
    price = prices.get(model)
    if price:
        input_cost_per_m = price["input"]
        output_cost_per_m = price["output"]
        input_cost = (tokens["input"] / 1000000.0) * input_cost_per_m
        output_cost = (tokens["output"] / 1000000.0) * output_cost_per_m
        total_cost = input_cost + output_cost
        print(f"\n{model}")
        print(
            f"Tokens: {tokens['input']} in / {tokens['output']} out / {tokens['total']} total"
        )
        print(f"Prices: input ${input_cost_per_m}/1M, output ${output_cost_per_m}/1M")
        print(
            f"Cost: ${total_cost:.6f} (input: ${input_cost:.6f}, output: ${output_cost:.6f})"
        )
        print(f"Cost for 1K email: ${(total_cost * 1000):.6f}")
        print(f"Cost for 40K emails: ${(total_cost * 40000):.2f}")
    else:
        print(f"\n{model}")
        print(
            f"Tokens: {tokens['input']} in / {tokens['output']} out / {tokens['total']} total"
        )
        print("Cost: Price not available")
