with open('web/schemas.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_fields = """    use_ollama: bool = False
    deepseek_key: str | None = None
    model: str | None = None
    thinking: bool = False
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)"""

new_fields = """    use_ollama: bool = False
    deepseek_key: str | None = None
    model: str | None = None
    api_url: str | None = None
    ollama_url: str | None = None
    ollama_model: str | None = None
    thinking: bool = False
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)"""

assert old_fields in text, "old_fields not found in web/schemas.py"
text = text.replace(old_fields, new_fields)

with open('web/schemas.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('web/schemas.py updated')
