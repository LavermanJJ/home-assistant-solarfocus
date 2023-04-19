# Contributing to Solarfocus Home Assistant Integration

There are several ways to contribute to this integration. Depending on your skill it could be beta testing, documenting, adding new registers, adding new functions.


## Contribution methods

### Direct edit via github.com
For small edits, like fixing typos, formating, etc. the edit could be done directly using the web github page. Choose the file and `Edit this file`. Github will guide you through the process. It must be considered that each change will lead to a pull request. Further testing is also not possible.

### Quick and Dirty 
1) Fork the this repository
2) create an additional branch (don't use the main)
3) make you changes
4) copy your changes manually (see [README.md -> Installation](README.md)) to your home assistant instance for testing (you can use the Home Assistant Visual Studio Code Add-on)
    - this method has the drawback, that you might modify something directly on your Home Assistant instance and forget to copy the change to your local repository.
    - for testing you can also install the modified integration from
    `https://github.com/YOURNAME/home-assistant-solarfocus`
5) push your changes to your forked repository
6) create a pull request from your branch

### Expert
Use the docker devcontainer workflow as described in [Home Assistant Developer Docs](https://developers.home-assistant.io/)

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