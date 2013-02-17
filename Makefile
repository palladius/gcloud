
help:
	@echo 'test:          Runs tests'

test:
	rake test

prepdeploy:
	rake manifest && rake build_gemspec
	echo Now check if theres any change to commit and push before release.

gemdeploy:
	rake manifest && rake build_gemspec && rake release && echo OK Correctly deployed
