# APAAR Verify (SIH26263), privacy-first student data verification for AICTE institutions
Thesis: "verify without exposing". Find duplicates/concurrent enrolment/intake overflow WITHOUT becoming a surveillance DB.
All data synthetic. Every flag is a review signal; NEVER auto-merge/reject/label fraud.
APAAR format is an UNVERIFIED configurable pattern (default 12 digits, no checksum). FORMAT_VALID != verified.
Mock verification provider always labelled MOCK. Placeholder rules labelled "placeholder" in UI.
Roles: OPERATOR, APPROVER (institution-scoped); AICTE_REVIEWER, AICTE_SUPERVISOR, ADMIN, AUDITOR.
Never-cut: tokens+encryption+RLS, linkage with per-field evidence, timeline rules, effective-dated intake, audit hash chain, baseline comparison.
Intake: use approval whose valid_during contains admission_date; missing/outdated => CANNOT_EVALUATE (never a flag).
