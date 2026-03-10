# Sentinel Project Makefile

analyze-bookmyshow:
	python -m sentinel.cli analyze demo_project/BookMyShow/src/main/java --use-llm

autogrow:
	python src/sentinel/gatekeeper/test_policy_autogrow.py

test:
	python -m unittest discover tests

# Usage: make end-to-end-test PROJECT=demo_project/BookMyShow/src/main/java
end-to-end-test:
	@echo "[EndToEnd] Running Sentinel analysis with LLM and saving report..."
	python -m sentinel.cli analyze $(PROJECT) --use-llm > tests/reports/analyze_$(notdir $(PROJECT))_$(shell date +%Y-%m-%d).txt
	@echo "[EndToEnd] Running policy autogrow..."
	python src/sentinel/gatekeeper/test_policy_autogrow.py
	@echo "[EndToEnd] Complete. Report saved to tests/reports/analyze_$(notdir $(PROJECT))_$(shell date +%Y-%m-%d).txt"
