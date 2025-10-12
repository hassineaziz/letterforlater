# 📜 Legacy Letter Web App

A full-stack web application that allows users to write heartfelt letters to loved ones and schedule them to be delivered after their death — verified by trusted contacts. Uses AI to assist in letter drafting and includes secure mechanisms to ensure letters are only sent under appropriate conditions.

---

## 🧠 Project Purpose

Legacy Letter enables people to leave behind meaningful, personalized messages for friends and family. It ensures these messages are:

- Authored thoughtfully (with optional AI help),
- Stored securely,
- Delivered only upon verified death or a set future date.

---

## 👑 Admin Access

The application includes a blog admin system for content management:

- **Admin Email**: `hassineaziz@icloud.com`
- **Admin Password**: `admin123!`
- **Admin Dashboard**: `/admin`

### After Database Reset

If you reset the database, the admin user will be automatically recreated. You can also manually ensure admin access by running:

```bash
python ensure_admin.py
```

---

## ✨ Core Features

### ✅ User Authentication

- Secure signup, login, logout
- Password reset functionality
- JWT-based sessions
- (Optional 2FA for future)

### 💌 Letter Creation & AI Drafting

- Multi-step letter creation wizard
- Collect recipient info, tone, topics, advice
- GPT-powered letter draft generation
- Manual editing and saving of drafts

### 📅 Scheduling & Delivery

- Schedule delivery by fixed date or death verification
- Periodic inactivity checks ("Are you still alive?" emails)
- Delivery triggered by date or by trusted contact confirmation

### 🤝 Trusted Contacts Management

- Add/edit/remove trusted contacts
- Trusted contacts receive secure confirmation links
- Death verification must be confirmed by trusted contacts

### 📬 Email Delivery & Notifications

- Secure email delivery of letters (inline or attachments)
- Email notifications for users and contacts
- Reminder emails for inactivity or unconfirmed letters

### 🧾 User Dashboard

- See all letters (draft, scheduled, delivered)
- Manage trusted contacts
- Update personal settings and preferences

---

## 🧑‍💻 Target Users & User Stories

### User Types

- 🧍 Regular Users (create/send letters)
- 🧑‍🤝‍🧑 Trusted Contacts (verify death)
- 📩 Recipients (receive letters)

### Example User Stories

| User                 | Goal                                                                      |
| -------------------- | ------------------------------------------------------------------------- |
| As a user            | I want to write letters with AI help to leave messages for my loved ones. |
| As a user            | I want to schedule these messages to be sent after I pass away.           |
| As a user            | I want to assign trusted contacts to confirm my death.                    |
| As a trusted contact | I want to securely verify a user’s death.                                 |
| As a recipient       | I want to receive a meaningful message after my loved one’s passing.      |

---

## 🏗️ Architecture Overview
