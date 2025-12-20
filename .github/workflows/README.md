# GitHub Actions Workflows

## Release Workflow

The `release.yml` workflow automatically builds both Debian (.deb) and AppImage packages when you create a new release tag.

### Automatic Release (Tag-based)

1. Update the version in `debian/changelog` using the `update-version.sh` script:
   ```bash
   ./update-version.sh 1.2.0
   ```

2. Commit the changes:
   ```bash
   git add debian/changelog
   git commit -m "Bump version to 1.2.0"
   ```

3. Create and push a tag:
   ```bash
   git tag v1.2.0
   git push origin master
   git push origin v1.2.0
   ```

4. The workflow will automatically:
   - Build a Debian package
   - Build an AppImage
   - Create a GitHub release with both artifacts
   - Generate release notes

### Manual Release (Workflow Dispatch)

You can also trigger the workflow manually from the GitHub Actions tab:

1. Go to Actions → Build and Release
2. Click "Run workflow"
3. Enter the version number (e.g., `1.2.0`)
4. Click "Run workflow"

The workflow will build the packages and create a release for the specified version.

## Workflow Details

### Jobs

1. **build-debian**: Builds the Debian package
   - Runs on Ubuntu latest
   - Installs build dependencies
   - Uses `dpkg-buildpackage` to create the .deb file
   - Uploads the package as an artifact

2. **build-appimage**: Builds the AppImage
   - Runs on Ubuntu 22.04 (for better compatibility)
   - Uses PyInstaller to bundle the application
   - Creates an AppImage using appimagetool
   - Uploads the AppImage as an artifact

3. **create-release**: Creates the GitHub release
   - Downloads artifacts from both build jobs
   - Generates release notes
   - Creates a GitHub release with both packages attached

### Artifacts

After a successful build, you'll find two artifacts:

- `brother-label-printer_VERSION_all.deb` - Debian package
- `brother-label-printer-VERSION-x86_64.AppImage` - Universal Linux package

## Testing Builds

To test the workflow without creating a release:

1. Push changes to a branch
2. Use the manual workflow dispatch option
3. Review the artifacts in the workflow run

## Requirements

The workflow requires:

- GitHub repository with write permissions
- `GITHUB_TOKEN` (automatically provided by GitHub Actions)
- Properly configured `debian/` directory
- Valid `requirements.txt` file

## Troubleshooting

### Build Failures

If the Debian build fails:
- Check that `debian/control` has all required dependencies
- Verify `debian/rules` is executable and correct
- Review the build log for specific errors

If the AppImage build fails:
- Check that all Python dependencies are in `requirements.txt`
- Verify that PyInstaller can find all modules
- Check for missing system libraries

### Release Creation Failures

If the release fails to create:
- Verify the tag format is `vX.Y.Z` (e.g., `v1.2.0`)
- Check that the repository has releases enabled
- Ensure you have push access to create releases

## File Structure

```
.github/
└── workflows/
    ├── release.yml          # Main release workflow
    └── README.md            # This file
```
