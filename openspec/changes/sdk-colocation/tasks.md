## Implementation Tasks

- [x] Move the three SDK distributions and their tests under `services/waygate/sdk`, `services/drover/sdk`, and `services/lumen/sdk`; remove standalone SDK source trees.
- [x] Update the service test command and repository-promotion documentation for the colocated SDK layout.
- [x] Regenerate and publish service subtree branches, then pin backend SDK dependencies and `backend/uv.lock` to released service-repository subdirectories.
- [x] Verify clean SDK installation from each published service repository and run the required repository test/lint gate.
- [ ] Push `dev`, archive this OpenSpec change, and push the archive commit.
