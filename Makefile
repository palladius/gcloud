
help:
	@echo 'test:          Runs tests'

test:
	rake test

gemdeploy:
	rake manifest && rake build_gemspec && rake release && echo OK Correctly deployed
