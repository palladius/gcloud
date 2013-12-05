
help:
	@echo 'test:          Runs tests'
	@echo 'install:       Installs official Google GCloud package!'

install:
	curl https://dl.google.com/dl/cloudsdk/release/install_google_cloud_sdk.bash | bash

test:
	rake test

prepdeploy:
	rake manifest && rake build_gemspec
	echo Now check if theres any change to commit and push before release.

gemdeploy:
	rake manifest && rake build_gemspec && rake release && echo OK Correctly deployed
