import ollama
import time

# Test both models
models = ["phi3", "llama3.2"]

for model in models:
    print(f"\nTesting {model}...")
    try:
        start = time.time()
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": "Say hello"}],
            options={"num_predict": 20}
        )
        elapsed = time.time() - start
        print(f"✅ {model} works! ({elapsed:.1f}s)")
        print(f"   Response: {response['message']['content'][:100]}")
    except Exception as e:
        print(f"❌ {model} error: {e}")
        