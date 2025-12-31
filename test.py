from cytolk import tolk

try:
    tolk.say("Testing Cytolk. Hello, NVDA.")
    print("Cytolk successfully initialized.")
except Exception as e:
    print(f"Error: {e}")
