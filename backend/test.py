from openai import OpenAI

client = OpenAI(
    api_key="rx-pjlsty0c2ok01wp8cn1z5oye9phlue9j",
    base_url="https://api.rudrxai.cloud/v1"
)

response = client.chat.completions.create(
    model="rudrx1-core",
    messages=[
        {"role":"user","content":"Hello"}
    ]
)

print(response.choices[0].message.content)