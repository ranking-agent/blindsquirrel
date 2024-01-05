import json

conversation_id = "815907e6-9a76-4da8-ab4e-cf35fa9c8ef6"

for i in range(14):
    with open(f"conversations/{conversation_id}/step_{i}.json", "r") as f:
        step = json.load(f)

    print(f"Step {i}")
    content = json.loads(step["response"]["choices"][0]["message"]["content"])
    print("New Observation Count", len(content["new_observations"]))
    print("Next Operation", content["action"])
    print("Next Argument", content["argument"])
    print("Input Tokens", step["response"]["usage"]["prompt_tokens"])
    print("Output Tokens", step["response"]["usage"]["completion_tokens"])
    print("Totalput Tokens", step["response"]["usage"]["total_tokens"])
    print("")
