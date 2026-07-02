# Dependency-tax audit (before adding any package)
Grounded in real incidents: left-pad 2016, event-stream 2018, chalk September 2025.

1. Count the transitive dependencies the package pulls in.
2. Write the 5 to 15 lines of native code that would replace it.
3. Name what the package can read or do if its maintainer is compromised.
4. Default to dropping it. Add it only if 1 to 3 still justify it, and record why in the changelog.
