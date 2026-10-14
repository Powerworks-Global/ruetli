.PHONY: run test eval reflect

# Delegates targets to track_2b (the HackApertus challenge root)
run:
	@$(MAKE) -C track_2b run

test:
	@$(MAKE) -C track_2b test

eval:
	@$(MAKE) -C track_2b eval

reflect:
	@$(MAKE) -C track_2b reflect

pdf:
	@$(MAKE) -C track_2b pdf
