# Sentinel Project Makefile

analyze-bookmyshow:
	python -m sentinel.cli end-to-end-test demo_project/BookMyShow

autogrow:
	@echo "Usage: python src/sentinel/gatekeeper/test_policy_autogrow.py --report tests/reports/<report>.txt"

unit-tests:
	python -m unittest discover tests

# Usage: make end-to-end-test PROJECT=demo_project/BookMyShow
end-to-end-test:
	@echo "[EndToEnd] Running Sentinel test workflow with Cohere-backed policy growth..."
	python -m sentinel.cli end-to-end-test $(PROJECT)
	@echo "[EndToEnd] Complete."

# Usage: make test PROJECT=demo_project/BookMyShow
test:
	@echo "[Test] Running Sentinel Guardian + Gatekeeper workflow..."
	python -m sentinel.cli test $(PROJECT)
	@echo "[Test] Complete."
