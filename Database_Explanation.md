# Database Architecture Overview

The application uses **SQLite3**, a lightweight, serverless relational database. The schema is defined in `backend/database.py` and uses a **Relational Data Model** with four tables. 

It is structured around a central `profiles` table, with three other tables maintaining a **One-to-Many (1:N)** relationship with the profile.

---

## Table Breakdown

### A. `profiles` (The Core Table)
Stores the primary identity and settings of the user.
* `id` *(TEXT, Primary Key)*: A secure, randomly generated 16-byte hex string (e.g., `e4d909c2...`).
* `created_at` *(TIMESTAMP)*: Automatically captures when the profile was generated.
* `name`, `phone`, `blood_group`: Basic demographic data.
* `template`: UI preference for how the profile looks when scanned.
* `password`: Used to hide sensitive medical data unless the person scanning enters it.
* `purpose`: Context of the QR tag (e.g., "Motorcycle Helmet", "Medical ID"). Used to calculate the baseline risk score.

### B. `emergency_contacts` (One-to-Many)
Stores the people to contact if the QR code is scanned in an emergency.
* `id` *(INTEGER, Primary Key, Auto-increment)*
* `profile_id` *(TEXT, Foreign Key)*: Links back to the `profiles` table.
* `contact_name`, `contact_phone`, `relation`: Details of the emergency contact.

### C. `medical_records` (One-to-Many with "Type" Column)
Consolidates all health-related data.
* `id` *(INTEGER, Primary Key, Auto-increment)*
* `profile_id` *(TEXT, Foreign Key)*
* `record_type` *(TEXT)*: Acts as an enum defining the row as either `'condition'`, `'allergy'`, or `'medication'`.
* `description` *(TEXT)*: The actual item (e.g., "Peanuts", "Hypertension").
* `severity` *(TEXT)*: How critical it is.

### D. `scan_logs` (One-to-Many)
Maintains an audit trail of every time a QR code is scanned.
* `id` *(INTEGER, Primary Key, Auto-increment)*
* `profile_id` *(TEXT, Foreign Key)*
* `scanned_at` *(TIMESTAMP)*: When the scan occurred.
* `ip_address`, `user_agent`: Extracts device and network info of the person who scanned it (useful for security and analytics).

---

## Interview Questions & How to Answer Them

Here is a curated list of questions you are highly likely to be asked about this specific database design during a technical interview, along with the best answers.

### Q1: "Why did you choose SQLite over MySQL, PostgreSQL, or MongoDB?"
**Your Answer:** 
> "I chose SQLite because it is serverless, requires zero configuration, and stores the entire database in a single file (`profiles.db`). This makes it incredibly fast for prototyping and highly portable. Since this application currently serves small-to-medium datasets without needing heavy concurrent write operations, SQLite is perfect. If the app scales to thousands of concurrent users, the schema is strictly relational, so migrating to PostgreSQL would be seamless."

### Q2: "Why is the `id` in the `profiles` table a Random Hex String instead of an Auto-Incrementing Integer?"
**Your Answer:** 
> "This is a critical security choice to prevent **IDOR (Insecure Direct Object Reference)**. If I used `id=1, id=2`, a malicious user who scans one QR code could easily guess the URL for `id=3` and view another person's private medical records. By using `secrets.token_hex(16)`, the URLs are mathematically impossible to guess, ensuring privacy by obscurity."

### Q3: "Why did you put conditions, allergies, and medications into a single `medical_records` table instead of making three separate tables?"
**Your Answer:** 
> "I used a design pattern called **Single Table Inheritance** (or Polymorphic design). Since conditions, allergies, and medications share the exact same attributes (`description`, `severity`, `profile_id`), creating three tables would violate the DRY (Don't Repeat Yourself) principle and require three separate database JOINs. By combining them and using a `record_type` flag, I simplified the schema and made queries much faster."

### Q4: "How are you handling the deletion of a profile? What happens to their medical records if a profile is deleted?"
**Your Answer:** *(Note: This is a slight critique of the current code, answering this shows deep knowledge)*
> "Currently, the Foreign Keys are standard. However, in a production environment, I would add `ON DELETE CASCADE` to the foreign keys in `medical_records`, `emergency_contacts`, and `scan_logs`. This ensures that if a user deletes their profile, all associated data is automatically purged from the database, preventing 'orphaned rows' and saving storage space."

### Q5: "How is the 'Patient Risk Score' handled in the database?"
**Your Answer:** 
> "The Patient Risk Score is **not** stored in the database. Instead, I calculate it dynamically in Python on the backend based on their `purpose`, `conditions`, and `allergies` at the time of the request. This is intentional: if our medical heuristic (the formula for determining risk) changes in the future, we don't have to write a script to update thousands of existing database rows. They will automatically be evaluated using the new rules."

### Q6: "How do you secure user passwords in this database?"
**Your Answer:** *(Note: Passwords in your `profiles` table are plain text right now)*
> "Right now, the password acts as a lightweight PIN to restrict viewing sensitive data on a scanned profile. However, moving forward, best practice dictates that we should never store plain-text passwords. I would upgrade this by implementing `bcrypt` or `Werkzeug.security` to hash the passwords before `INSERT`, and verify the hash during the `POST` request."

### Q7: "What is the purpose of the `scan_logs` table?"
**Your Answer:** 
> "It serves two purposes: **Analytics and Security**. On the Admin Dashboard, we can query this table to see peak scan times and total usage (Analytics). For Security, it logs the IP address and User-Agent. If a user suspects their QR code was scanned maliciously, we have an audit trail of exactly when and what device scanned it."
