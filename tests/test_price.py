from app.domain.realestate.detection_utils_llm import extract_price

# Testar valores por extenso
tests = [
    "cem mil",
    "um milhão",
    "um milhao",
    "100.000,00",
    "1000000"
]

for test in tests:
    result = extract_price(test)
    print(f"'{test}' → {result}")
