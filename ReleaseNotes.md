<img align="right" width="250" height="47" src="https://raw.githubusercontent.com/gematik/gematik.github.io/master/Gematik_Logo_Flag_With_Background.png" />
<br />

# Release Notes

EU Web Portal

## Unreleased

### added

- Added application navigation to the portal header.
- Added country selection with local flag images.
- Added a reusable Lit ISM application component with support for independent
  search fields and choice-based alternatives.
- Added separate public and internal ISM datasets selected through application
  build configurations. Public examples are the default.
- Added generated fictional flags and embedded demonstration help images.

### changed

- Displayed the gematik logo in the portal footer.
- Used the portal name as the header link.
- Removed the MyHealth@EU logo and browser tab icon pending rights clarification.
- Prefer emoji flags for real countries, with automatic local SVG fallback
  and application configuration instead of a display checkbox.
- Load the country selector from the selected dataset instead of a fixed list.

### fixed

- Removed the default favicon.

### other

- Documented ISM coverage, acceptance criteria, and source inventory.
