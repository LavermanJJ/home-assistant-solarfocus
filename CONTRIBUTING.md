# Contributing to Solarfocus Home Assistant Integration

Thank you for considering contributing to the Home Assistant Solarfocus Custom Component. Before you get started, please read through this guide to ensure that your contributions can be accepted as quickly and easily as possible.There are several ways to contribute to this integration. Depending on your skill it could be beta testing, documenting, adding new registers, adding new functions.

## Reporting Issues

If you encounter any problems with the Home Assistant Solarfocus Custom Component, please create a GitHub Issue in the project's repository. When creating an issue, please provide as much detail as possible, including:

1. A clear and descriptive title
2. A detailed description of the issue
3. Steps to reproduce the issue
4. Any relevant error messages or log output
5. Your Home Assistant and Solarfocus integration and firmware versions

## Contributing Code

If you're interested in contributing code to the Home Assistant Solarfocus Custom Component, please follow these steps:

1. Fork the project's repository.
2. Create a new branch for your changes.
3. Make your changes in the new branch.
4. Verify your changes (see Testing section)
6. Submit a pull request.

Please ensure that your code adheres to the following guidelines:

* Ensure that your code is well-documented.
* Avoid breaking changes whenever possible.
* Keep your pull request small and focused on a single issue or feature.

### Testing

#### Using devcontainer (recommended)

To make development easier and more consistent across contributors, we recommend using the devcontainer setup provided by Home Assistant. This allows you to run Home Assistant Core in a Docker container and use Visual Studio Code as your development environment. For more information, please see the [Home Assistant Development Environment documentation](https://developers.home-assistant.io/docs/development_environment#developing-with-visual-studio-code--devcontainer).

* copy `custom_components/solarfocus` folder to `core/config/` directory.
* once testing is done, make sure to copy the changes back to the git repository.


#### Test on production (not recommended)

Copy your changes manually (see [README.md -> Installation](README.md)) to your home assistant instance for testing (you can use the Home Assistant Visual Studio Code Add-on)
    - this method has the drawback, that you might modify something directly on your Home Assistant instance and forget to copy the change to your local repository.
    - for testing you can also install the modified integration from
    `https://github.com/YOURNAME/home-assistant-solarfocus`


## Remarks - Important Files

- [hacs.json](https://github.com/LavermanJJ/home-assistant-solarfocus/blob/main/hacs.json): name, version definition for the hacs integration (see [HACS Integrations](https://hacs.xyz/docs/publish/integration/)), modify if you plan to install the integration from your fork, don't use this branch to make a pull request to the original repository.

- [custom_components/solafocus/manifest.json](https://github.com/LavermanJJ/home-assistant-solarfocus/blob/main/custom_components/solarfocus/manifest.json): if you go deeper into the development you might need to update the used pysolarfocus python package. To test you can modifiy the requirements to used your own version: e.g.,
  `"requirements": ["git+https://github.com/lein1013/pysolarfocus.git@develop#pysolarfocus==3.4.2", "pymodbus==3.1.2"],`

- [strings.json](https://github.com/LavermanJJ/home-assistant-solarfocus/blob/main/custom_components/solarfocus/strings.json): relevant for enums and translation (see the related translations folder). Keep consistent. Some guides:
    - First letter is capital
    - do the changes also in the tranlations files (en,de.json)


## Usefull links 
- [HACS Development](https://hacs.xyz/docs/developer/start)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Home Assistant Integration File Structure](https://developers.home-assistant.io/docs/creating_integration_file_structure)
- [Home Assistant Developer Environment](https://developers.home-assistant.io/docs/development_environment/
)
- [Home Assistant Translation](https://developers.home-assistant.io/docs/internationalization/core)

## Code of Conduct

We are committed to providing a friendly, safe, and welcoming environment for all, regardless of gender, sexual orientation, ability, ethnicity, religion, or other personal characteristics. By participating in this project, you agree to abide by our Code of Conduct.

## License

By contributing to the Home Assistant SolarFocus Custom Component, you agree that your contributions will be licensed under the project's Apache-2.0 License.
