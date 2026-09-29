## Integration Checklist

Before requesting a review or merging into `main`, please ensure you have completed the following:

- [ ] **Tests:** I have written tests for my changes and verified they pass.
- [ ] **Integration Gates:** I ran `make check` locally and it completed successfully.
- [ ] **Ownership Boundaries:** My PR respects the boundaries in `.github/CODEOWNERS`. (If I touched another teammate's file, I have addressed the `check_ownership.py` warning).
- [ ] **Contracts:** `check_contracts.py` passes (schema drift is prevented).
- [ ] **Documentation:** I have updated documentation and logged my continuous integration in `docs/INTEGRATION_LOG.md` if applicable.

### `make check` Output
<details>
<summary>Paste the output of `make check` here</summary>

```
# PASTE HERE
```

</details>
