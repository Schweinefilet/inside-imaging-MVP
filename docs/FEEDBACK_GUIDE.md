# Feedback System - User Guide

## Overview
The Inside Imaging feedback system allows radiologists, radiographers, and users to submit corrections, report errors, and suggest improvements directly through the platform.

---

## For Users/Radiologists

### Accessing the Feedback Form
1. Log in to your account
2. Navigate to **Profile** (top right menu)
3. Scroll down to the **"Submit Feedback or Correction"** section

### Submitting Feedback
Fill out the form with the following fields:

**1. Feedback Type** (Required)
- **Translation Error:** Incorrect medical translation
- **Medical Term Definition:** Missing or wrong term explanation
- **UI Bug:** Interface or display issues
- **Feature Request:** New functionality suggestions
- **Other:** General feedback

**2. Subject** (Required)
- Brief one-line summary
- Example: "Incorrect Kiswahili translation for 'atelectasis'"

**3. Original Text** (Optional)
- Copy the incorrect text from the report
- Example: "atelectasis ni ugonjwa wa mapafu"

**4. Corrected Text** (Optional)
- Provide the correct version
- Example: "atelectasis ni kukunjika kwa mapafu"

**5. Additional Details** (Optional)
- Explain the context or reasoning
- Reference medical sources if applicable
- Describe steps to reproduce bugs

**6. Submit**
- Click **"Submit Feedback"** button
- You'll receive a confirmation message

### Tracking Your Submissions
Below the form, you'll see a **"Your Feedback Submissions"** table showing:
- **Type:** Category of feedback
- **Subject:** Your summary
- **Status:** 
  - 🟡 **PENDING** - Under review
  - 🟢 **APPROVED** - Acknowledged, will implement
  - 🔵 **IMPLEMENTED** - Changes made to platform
  - 🔴 **REJECTED** - Not applicable or won't fix
- **Submitted:** Date and time
- **Notes:** Admin response or explanation

---

## For Admins

### Accessing Admin Dashboard
1. Log in with admin credentials (username: `admin` or `radiologist`)
2. Navigate to **Profile**
3. Click **"📋 Review All Feedback (Admin)"** button at bottom

### Reviewing Feedback
**Status Filter Tabs:**
- **Pending:** New submissions requiring review
- **Approved:** Acknowledged items for implementation
- **Implemented:** Completed changes
- **Rejected:** Declined submissions
- **All:** Complete feedback history

**Feedback Cards Display:**
- Username and submission date
- Feedback type badge
- Status badge (color-coded)
- Original text (if provided) - red border
- Corrected text (if provided) - green border
- User description
- Admin notes (if reviewed)
- Review form (pending items only)

### Processing Feedback
For **PENDING** items, you'll see a review form at the bottom:

**1. Add Admin Notes** (Optional)
- Explain your decision
- Reference implementation PR/commit
- Provide reasoning for rejection

**2. Choose Action:**
- **✓ Approve** - Mark for implementation queue
- **✓ Implemented** - Changes already deployed
- **✗ Reject** - Not applicable or duplicate

**3. Submit Review**
- User will see status update in their feedback history
- Timestamp and reviewer username are recorded

---

## Workflow Diagram

```
USER SUBMITS FEEDBACK
         ↓
   STATUS: PENDING
         ↓
  ADMIN REVIEWS ────→ [Reject] → STATUS: REJECTED
         ↓
    [Approve]
         ↓
  STATUS: APPROVED
         ↓
 IMPLEMENT CHANGES
         ↓
  MARK AS IMPLEMENTED
         ↓
STATUS: IMPLEMENTED
```

---

## Use Cases

### Example 1: Translation Correction
**User Report:**
- Type: Translation Error
- Subject: "Pneumothorax translation incorrect"
- Original: "pneumothorax ni hewa katika kifua"
- Corrected: "pneumothorax ni hewa katika uja wa mapafu"
- Description: "Current translation refers to general chest air, but should specify pleural space"

**Admin Action:**
- Review medical terminology
- Verify with Kiswahili medical dictionary
- Update `src/translate.py` with corrected translation
- Mark as **IMPLEMENTED**
- Add note: "Fixed in commit abc123, deployed 2025-01-20"

### Example 2: Missing Medical Term
**User Report:**
- Type: Medical Term Definition
- Subject: "Add definition for 'pleural effusion'"
- Description: "Patients often don't understand this term. Need simple explanation"

**Admin Action:**
- Add to `_TERM_DEFS` in `src/translate.py`:
  ```python
  "pleural effusion": "Fluid buildup between lung and chest wall layers"
  ```
- Mark as **IMPLEMENTED**
- Add note: "Added to glossary with layman's explanation"

### Example 3: UI Bug Report
**User Report:**
- Type: UI Bug
- Subject: "Body diagram not showing in light mode"
- Description: "After switching to light theme, body silhouette disappears completely"

**Admin Action:**
- Investigate `templates/result.html` CSS
- Identify color contrast issue with `--body-fill`
- Fix theme token values
- Mark as **IMPLEMENTED**
- Add note: "Fixed body-fill colors for better contrast in both themes"

---

## Best Practices

### For Users
✅ **DO:**
- Be specific and detailed
- Include screenshots if possible (future feature)
- Reference exact text when reporting errors
- Provide medical sources for corrections
- One issue per submission

❌ **DON'T:**
- Submit duplicate reports (check your history first)
- Include patient-identifying information (PHI)
- Submit general complaints without actionable details
- Combine multiple unrelated issues

### For Admins
✅ **DO:**
- Review submissions within 48 hours
- Provide clear reasoning for rejections
- Reference implementation commits/PRs
- Keep users informed with detailed notes
- Mark items as IMPLEMENTED promptly after deployment

❌ **DON'T:**
- Approve without verifying accuracy
- Reject without explanation
- Leave items in PENDING indefinitely
- Implement changes without testing

---

## Database Schema Reference

```sql
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,              -- Submitting user
    feedback_type TEXT NOT NULL,         -- Category
    subject TEXT NOT NULL,               -- Brief summary
    original_text TEXT,                  -- Incorrect version
    corrected_text TEXT,                 -- Proposed fix
    description TEXT,                    -- Detailed explanation
    status TEXT DEFAULT 'pending',       -- pending, approved, implemented, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,               -- Admin review date
    reviewed_by TEXT,                    -- Admin username
    admin_notes TEXT                     -- Admin response
);
```

---

## API Reference (Future)

When building external integrations, use these endpoints:

### `POST /submit-feedback`
Submit new feedback (requires authentication)

**Form Data:**
- `feedback_type`: string (required)
- `subject`: string (required)
- `original_text`: string (optional)
- `corrected_text`: string (optional)
- `description`: string (optional)

**Response:**
- Redirects to profile with success/error flash message

### `GET /feedback-admin?status=pending`
Admin dashboard (requires admin privileges)

**Query Params:**
- `status`: string (pending|approved|implemented|rejected|all)

**Response:**
- HTML page with filtered feedback list

### `POST /review-feedback/<id>`
Admin review action (requires admin privileges)

**URL Params:**
- `id`: integer (feedback ID)

**Form Data:**
- `status`: string (approved|implemented|rejected)
- `admin_notes`: string (optional)

**Response:**
- Redirects to feedback-admin with success/error flash message

---

## Troubleshooting

### Problem: "Access denied. Admin privileges required."
**Solution:** You need admin account. Username must be `admin` or `radiologist`. Contact system administrator.

### Problem: Feedback form not appearing on profile
**Solution:** Ensure you're logged in. Refresh page and clear browser cache.

### Problem: Status not updating after admin review
**Solution:** Hard refresh page (Ctrl+F5 or Cmd+Shift+R). Check database with:
```bash
sqlite3 data/patient_data.db "SELECT * FROM feedback WHERE id=<YOUR_ID>;"
```

### Problem: Can't see older feedback submissions
**Solution:** All submissions persist in database. Scroll down in feedback history table on profile page.

---

## Future Enhancements

Planned features for v2.0:

- [ ] **Email Notifications**
  - Alert admins on new submissions
  - Notify users when status changes
  
- [ ] **Screenshot Attachments**
  - Upload images with bug reports
  - Store in `static/feedback/` directory
  
- [ ] **Voting System**
  - Upvote popular feature requests
  - Prioritize based on votes
  
- [ ] **Public Feedback Board**
  - Transparent roadmap for community
  - Read-only access to approved items
  
- [ ] **GitHub Integration**
  - Auto-create GitHub Issues from feedback
  - Link feedback to PRs/commits
  
- [ ] **Bulk Actions**
  - Select multiple items for approval/rejection
  - Export feedback as CSV

---

*Last Updated: 2025-01-XX*  
*Inside Imaging MVP - Feedback System Documentation*
