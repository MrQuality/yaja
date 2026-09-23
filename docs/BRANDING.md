# YAJA naming and third-party references

## Project identity

Use **YAJA** as the project name and **Project and task management** as the
descriptor. YAJA does not need an expanded acronym. Keep the repository name
and existing `yaja` package namespace.

Use **YAJA query language** or **query filters** for the project's own grammar,
`yaja_query` for the Rust crate, and `CompiledQueryArtifact` for the shared
compiled-query contract. The proposed browser module is `yaja-query`.

The Rust crate name, import path, source directory, and TypeScript interface
have changed together. Consumers must update imports and type references;
parser behavior and the contract's fields are unchanged. No legacy aliases
are provided in this early-development repository.

## Compatibility and references

The implemented parser accepts one equality filter. Jira Query Language (JQL)
compatibility is not a current feature or requirement. The compiler design is
for YAJA's own grammar. A future interoperability proposal must specify the
supported syntax and semantics, differences, independent implementation sources,
and compatibility tests before making public compatibility claims.

Third-party product names may appear in necessary, accurate comparison,
interoperability, source attribution, or license documentation. Do not imply
endorsement, sponsorship, or compatibility that has not been established. Keep
YAJA's name and visual identity distinct. Use original or appropriately licensed
artwork; do not copy another product's logos, screenshots, or fonts without the
necessary rights. Preserve required third-party notices rather than blindly
replacing product names in them.

Where Jira is discussed publicly, use this independence notice:

> YAJA is an independent project and is not affiliated with, sponsored by, or
> endorsed by Atlassian. Jira is a trademark of Atlassian.

A notice and a naming scan do not establish legal clearance. Relevant policy
references include [Atlassian's trademark guidelines](https://www.atlassian.com/legal/trademark)
and its [JQL documentation](https://support.atlassian.com/jira-software-cloud/docs/use-advanced-search-with-jira-query-language-jql/).

## Release review

Before publishing a release, maintainers should:

- Review the repository description, topics, website, domains, package listings,
  release text, social profiles, and downloadable artifacts for consistent
  current branding and accurate feature claims.
- Record the source and applicable license of third-party code, grammar files,
  examples, documentation, and visual assets; retain required notices. A local
  source scan alone cannot establish provenance.
- Obtain appropriate trademark clearance for YAJA and any logo in the intended
  markets. No clearance or trademark availability is asserted by this policy.
- Assess historical releases separately when necessary. Do not rewrite shared
  history merely to change historical naming.

The repository checks current naming, not external properties, historical
artifacts, legal rights, or the completeness of compatibility claims. External
brand review, provenance verification, and trademark clearance remain release
responsibilities.
