# SOP-03 Triage Status Workflow (Fictional Training SOP)

Fictional procedure for the training prototype.

## 1. Lifecycle
Every report follows the lifecycle New, then In Review, then Closed. Statuses cannot be skipped and a Closed report is terminal. Moving a report backwards is not permitted.

## 2. Starting Review
An operator or reviewer moves a report from New to In Review once all mandatory fields are confirmed complete. Each transition is recorded with the actor code and a UTC timestamp.

## 3. Closure Approval
Closing a report requires a human-in-the-loop compliance approval. The request is placed in the Triage Approvals queue and the record is frozen until a reviewer approves or rejects it with a written justification. The reviewer must be a different person from the requester (separation of duties).

## 4. Rejected Closure
If closure is rejected the report remains In Review. The requester addresses the reviewer's justification and may submit a new closure request.
