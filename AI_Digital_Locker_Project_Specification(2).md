# AI Digital Locker

## 1. Project Overview

**AI Digital Locker** is a cloud-based digital document management application designed primarily for personal use. It is a **college-level project and portfolio project**, not a production-scale public service.

The project has two client applications:

- A **Django web application**.
- A **Windows desktop application** built with **Tkinter**.

Both clients will share the same core document-management capabilities while allowing platform-specific features where appropriate. The desktop application is a cloud client and can optionally keep selected files as local offline copies.

Both applications communicate with a common **FastAPI backend**. **Supabase** provides the PostgreSQL database and cloud file storage. **Google Sheets**, if retained in the final implementation, is an administrative document registry/reporting layer rather than the primary database or file store.

The application includes two AI choices in its interface:

- **Cloud AI — OpenRouter:** the primary AI option that will actually be implemented and used.
- **Local AI:** a placeholder/future option for now. It will not have a local inference backend in this project stage. The interface must not imply that local inference works when it does not.

The AI assistant supports document understanding and document management. It is a supporting feature; the digital locker remains the central product.

The project should use sensible, practical security and access controls appropriate for a college and portfolio project. It does not aim to implement bank-grade or enterprise-scale security infrastructure, and unnecessary complexity should be avoided.

------------------------------------------------------------------------

## 2. Main Goals

The project aims to provide:

- A simple account-based digital locker intended primarily for personal use.
- Cloud storage for personal documents using Supabase Storage.
- A Django web client and a Tkinter Windows desktop client with the same core features and platform-specific capabilities.
- A common FastAPI backend for both clients.
- A 500 MB cloud-storage limit per user.
- Optional local/offline copies of selected documents on the desktop device.
- An AI assistant for document understanding and management.
- OpenRouter as the primary, implemented cloud AI option.
- A Local AI option visible as a placeholder only; local model inference is out of scope for the current version.
- Practical account separation and access controls suitable for a college-level project.
- Google Sheets document reporting and a single administrator, as described later in this specification, subject to final scope confirmation.

The implementation should prioritize working features, clear architecture, and a manageable scope over unnecessary enterprise infrastructure.

------------------------------------------------------------------------

# 3. User Accounts

## Registration and Login

Users create an account using only:

-   Email
-   Password

There is no separate username field.

The user's email identifies the account.

### Example

``` text
Email: chaitanya@example.com
Password: ********
```

Users can then access their own documents through either the web
application or the desktop application.

------------------------------------------------------------------------

# 4. User Dashboard

The user dashboard should provide a simple overview of the account.

Example:

``` text
Chaitanya
chaitanya@example.com

Documents: 24
Storage: 183 MB / 500 MB
```

The dashboard should also provide access to the user's uploaded
documents, upload functionality, search/management functionality,
settings, and the AI assistant.

The interface should remain simple rather than becoming a complex
document-management suite.

------------------------------------------------------------------------

# 5. Document Storage

## Cloud Storage

Cloud storage is the normal/default storage mode.

The actual uploaded files are stored using **Supabase Storage**.

Document information and metadata are stored in the **Supabase
PostgreSQL database**.

The application therefore separates:

``` text
Supabase PostgreSQL
        ↓
Document metadata

Supabase Storage
        ↓
Actual uploaded files
```

Google Drive is **not** used for file storage.

## Storage Limit

Each user has a maximum cloud storage allowance of:

**500 MB**

The application should display the user's current usage.

Example:

``` text
Storage
183 MB / 500 MB
```

Before uploading a file, the system should check whether enough storage
remains.

------------------------------------------------------------------------

# 6. Uploading Documents

The normal upload workflow should remain simple.

``` text
Select file
    ↓
Validate file
    ↓
Check storage limit
    ↓
Upload to cloud storage
    ↓
Store document metadata
    ↓
Upload complete
```

The AI should **not automatically analyze every document immediately
after upload**.

AI assistance is available when the user chooses to use it.

------------------------------------------------------------------------

# 7. Supported Documents

The locker is intended to allow users to store different kinds of files,
including:

-   PDF
-   DOCX
-   TXT
-   XLSX
-   Images
-   Other common document/file formats where supported

The system is primarily a **storage and management application**, so
files do not need to be transformed into a special format before being
stored.

------------------------------------------------------------------------

# 8. Duplicate Filenames

Duplicate filenames are allowed.

For example, a user may upload:

``` text
certificate.pdf
certificate.pdf
certificate.pdf
```

These should be treated as separate uploaded documents.

Each stored document will have its own internal unique identifier, even
if multiple documents have the same visible filename.

The system should not reject a file simply because another file
belonging to the same user has the same filename.

------------------------------------------------------------------------

# 9. Document Organization

The project intentionally does **not** use a folder hierarchy.

Users will work with a single document collection and can use basic
operations such as:

-   Search
-   Sort
-   Filter
-   Upload
-   Download
-   Rename
-   Delete

There is no requirement for:

``` text
Education/
Finance/
Personal/
Certificates/
```

or similar folder structures.

------------------------------------------------------------------------

# 10. File Access

Users should be able to download their stored documents.

The project does not require a complex online document editor.

The main file workflow is:

``` text
Upload → Store → Access/Download
```

------------------------------------------------------------------------

# 11. Offline Storage

Cloud storage remains the primary storage mechanism, but users can
optionally keep selected files as local offline copies.

The upload interface can provide an option such as:

``` text
☑ Cloud Storage
☐ Keep Offline Copy
```

The offline copy is stored on the user's current computer.

The project does **not** attempt to implement cross-device offline
synchronization.

For example, if a document is kept offline on one computer, that does
not mean another computer automatically receives the offline copy.

Offline storage is simply an additional local copy for that device.

------------------------------------------------------------------------

# 12. AI Assistant

The project includes an AI assistant for document understanding and document-management tasks.

## AI Options

The interface will offer two options:

### Cloud AI — OpenRouter

- This is the primary AI option and the only AI option intended to work in the current project version.
- The application will use a selected model through OpenRouter. The exact model and configuration can be decided during implementation.
- The AI may need document text or relevant excerpts to answer questions about a document. The interface and project documentation should not claim that cloud AI processing is local or that document content is never sent to an external provider.
- API credentials must be kept out of frontend code and distributed desktop-client code. The final credential arrangement (application-managed key versus user-provided key) remains to be decided.

### Local AI — Placeholder Only

- The UI may show Local AI as an option to communicate the intended future capability.
- No local model, inference runtime, or local AI backend will be implemented at this stage.
- The UI should clearly mark this option as unavailable, planned, or coming soon. It must not pretend that a local model is running.
- Selecting Local AI must not silently route requests to Cloud AI while claiming they are local.

## Privacy and Scope

Documents are stored in the cloud. Because OpenRouter is the primary working AI option, content needed for an AI request may be transmitted to OpenRouter and the selected model provider. The implementation should send only the content reasonably needed for the task where practical and explain this behavior clearly.

The project is a college-level personal-use application. It should use sensible security practices, but it does not require a bank-grade or enterprise-scale AI security architecture. The local AI option is a UI placeholder, not a privacy-preserving local-processing mode in the current version.

------------------------------------------------------------------------

# 13. AI User Interface

The AI assistant will appear as a small floating button near the bottom-right of the application interface.

When clicked, it opens a compact chat window. The interface should make the selected AI option visible and should distinguish the working **Cloud AI (OpenRouter)** option from the **Local AI placeholder**.

The Local AI option must be labelled as unavailable/planned until a real local inference backend is implemented. Cloud AI should be the default working option.

The AI should only be initialized or called when the user opens or uses the assistant, rather than continuously running in the background.

------------------------------------------------------------------------

# 14. AI Capabilities

The AI is intended to help with lightweight document-management tasks.

### Search

Example:

> "Find my internship certificate."

The AI can interpret the request and use the application's
document-search functionality.

### Document Reading

The AI can access the contents of documents when required and provide
information from them.

### Information Retrieval

Example:

> "What is the registration number in this document?"

### Summarization

Example:

> "Give me a short summary of this document."

### Filename Suggestions

Example:

``` text
Current:
IMG_28371.pdf

Suggested:
Python_Internship_Certificate.pdf
```

### Document Assistance

The AI can help users understand or locate information contained in
their stored documents.

The AI should not be treated as an unrestricted system administrator or
given unrestricted access to the computer.

------------------------------------------------------------------------

# 15. AI and Document Modification

The AI can **suggest** changes, but it should not silently modify user
files.

For example:

``` text
Current filename:
IMG_28371.pdf

AI suggestion:
Python_Internship_Certificate.pdf

        [Cancel]   [Rename]
```

The user must explicitly confirm the action before the application
performs the rename.

The same principle applies to other modifying/destructive operations
that may later be exposed through the AI.

The AI should not independently delete, rename, move, or otherwise
modify documents without user confirmation.

------------------------------------------------------------------------

# 16. AI and Backend Access

The AI should not receive unrestricted raw access to the database. Instead, the application should expose controlled document-search and document-management operations through FastAPI.

Conceptually:

```text
User
  ↓
AI Assistant (Cloud AI via OpenRouter)
  ↓
Controlled FastAPI operation / document context
  ↓
Supabase database and storage, as permitted
  ↓
Relevant result or document text
  ↓
OpenRouter model response
  ↓
User
```

The exact request flow may vary by feature, but document access must remain scoped to the authenticated user's account. The AI should use application-provided operations rather than receive unrestricted database credentials.

When document content is needed for a Cloud AI request, the application should pass only the relevant content reasonably necessary for the task where practical. The user should not be told that this content is processed locally: Cloud AI requests use OpenRouter.

The Local AI option has no backend in the current project version and must not be represented as operational.

------------------------------------------------------------------------

# 17. AI Installation and Availability

The basic locker must remain usable even when the AI assistant is not used or Cloud AI is unavailable.

- **Cloud AI:** implemented through OpenRouter, with model selection/configuration finalized during implementation.
- **Local AI:** UI placeholder only; no model files, local runtime, inference service, or local backend are required in this version.

Do not bundle a local model with the application for the current scope.

------------------------------------------------------------------------

# 18. Web Application

The web version will be developed using **Django**.

The web application will provide the user-facing interface for functions
such as:

-   Account access
-   Dashboard
-   Document list
-   Upload
-   Download
-   Search
-   Basic document management
-   AI assistant
-   Storage information
-   Account/settings access

Django is responsible for the web-facing application experience.

------------------------------------------------------------------------

# 19. Desktop Application

A Windows desktop version will be created using **Tkinter**.

The application will be launched as a Python application, for example:

``` text
python locker.py
```

The desktop interface is intentionally simple.

It will provide access to the same user's cloud account and documents
through the common backend.

The desktop application will also provide the AI assistant and
offline-copy functionality.

------------------------------------------------------------------------

# 20. FastAPI Backend

**FastAPI** will act as the central backend/API layer.

Both the Django web application and Tkinter desktop application will
communicate with the backend.

Conceptually:

``` text
Django Web App
       │
       ↓
    FastAPI
       ↑
       │
Tkinter Desktop App
```

FastAPI handles communication between the user interfaces and the
application's cloud services.

It also provides controlled operations for document management and
AI-related functionality.

------------------------------------------------------------------------

# 21. Supabase

**Supabase** is the central cloud platform used by the project.

It provides:

### PostgreSQL Database

Used for application data and document metadata.

### Storage

Used to store the actual uploaded documents.

The project does not use Google Drive for document storage.

Supabase is selected to keep the cloud database and file-storage
components together rather than introducing several separate cloud
platforms.

------------------------------------------------------------------------

# 22. Google Sheets Administration

Google Sheets is used only as an **administrative document
registry/reporting layer**.

It is not the primary database.

The administrator should have a Google Sheet containing document
information such as:

``` text
Document ID
User Email
Filename
File Type
File Size
Upload Time
Last Modified
Storage Mode
```

The sheet should update automatically as document records change.

For example:

``` text
User uploads file
      ↓
Supabase / application data updated
      ↓
Google Sheet updated
```

The project does not require a separate user-information sheet.

------------------------------------------------------------------------

# 23. Administrator

There is only **one administrator**.

The administrator is identified by the administrator's own email
account.

Normal users cannot assign themselves administrator privileges.

The administrator can access the administrative functionality and can
open/download stored user documents as required by the project.

The admin interface can provide document-related information and access
to the automatically maintained Google Sheet.

No multi-admin system is required.

------------------------------------------------------------------------

# 24. Security and Access Model

The project should maintain basic account-level separation.

A normal user should only be able to access documents belonging to their
own account.

Conceptually:

``` text
User A
 ├── Document 1
 ├── Document 2
 └── Document 3

User B
 ├── Document 4
 └── Document 5
```

User A should not be able to access User B's documents through normal
application operations.

The administrator is the designated exception.

The project uses basic email/password authentication and does not
require:

-   OTP
-   Two-factor authentication
-   Phone verification
-   Multiple administrators

------------------------------------------------------------------------

# 25. Sharing

Document sharing is **not part of the project**.

Users cannot generate public document-sharing links for other people.

Documents remain associated with their respective user accounts.

------------------------------------------------------------------------

# 26. High-Level Architecture

``` text
                         AI DIGITAL LOCKER
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
          Django Web App                Tkinter Desktop App
                 │                             │
                 └──────────────┬──────────────┘
                                │
                             FastAPI
                                │
                    ┌───────────┴───────────┐
                    │                       │
                 Supabase             OpenRouter
                    │                 Cloud AI
             ┌──────┴──────┐
             │             │
         PostgreSQL      Storage
         Metadata        Documents
                    │
                    ↓
             Google Sheets
              Admin Registry

Local AI is shown only as a future UI option; it has no runtime/backend in this version.
```

The architecture is intentionally simple and does not use unnecessary
distributed infrastructure.

------------------------------------------------------------------------

# 27. Main Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Programming language | Python | Main development language |
| Web framework | Django | Web application and user-facing web experience |
| Backend/API | FastAPI | Shared API, controlled document operations, and integration layer |
| Desktop GUI | Tkinter | Windows desktop client |
| Cloud database | Supabase PostgreSQL | Application data and document metadata |
| Cloud storage | Supabase Storage | Actual uploaded files |
| Cloud AI | OpenRouter | Primary, implemented AI assistant option |
| Local AI | UI placeholder only | Future option; no inference backend in the current version |
| Administration/reporting | Google Sheets | Automatic document registry/reporting, if retained in final scope |

The web and desktop clients share core capabilities, while desktop-only offline copies and other platform-specific details may differ.

------------------------------------------------------------------------

# 28. Technologies Intentionally Not Used

To keep the project manageable, the design does not require:

- Google Drive for document storage.
- MongoDB, Redis, or Kafka.
- Vector databases unless a later, explicit requirement justifies one.
- Microservices or complex distributed infrastructure.
- A local AI inference backend or bundled local model in the current version.
- A large custom AI infrastructure; the primary AI integration is OpenRouter.
- Cross-device offline synchronization.
- Document-sharing links.
- Folder-management systems.
- Multi-admin infrastructure.
- Bank-grade or enterprise-scale security infrastructure.

The project should still implement sensible authentication, authorization, secret handling, and user-level document separation. Keeping the scope small does not mean ignoring basic security.

------------------------------------------------------------------------

# 29. Expected User Flow

A typical user interaction can look like:

``` text
Create account
     ↓
Login
     ↓
Dashboard
     ↓
Upload document
     ↓
Store in cloud
     ↓
Document appears in locker
     ↓
Search / Download / Manage
     ↓
Optionally open AI assistant
     ↓
Ask about a document
     ↓
AI provides information or a suggestion
     ↓
User confirms any modifying action
```

------------------------------------------------------------------------

# 30. Expected Project Outcome

The final project should demonstrate a practical Python-based digital document management system with:

- Email/password account access.
- Cloud document storage through Supabase.
- A 500 MB per-user storage limit.
- Document upload, download, search, and basic management.
- Support for duplicate filenames.
- Optional local offline copies on the desktop device.
- A Django web client.
- A Tkinter Windows desktop client.
- A shared FastAPI backend.
- A cloud AI assistant using OpenRouter for document understanding and management.
- A Local AI option that is clearly presented as a placeholder and is not falsely represented as working.
- User confirmation for AI-suggested modifying/destructive actions.
- Practical user-level access separation.
- Google Sheets reporting and a single administrator if these remain in the final agreed scope.

The objective is a manageable but distinctive college and portfolio project combining web development, API development, desktop GUI development, cloud storage, database management, and a practical cloud AI integration.

------------------------------------------------------------------------

# 31. Scope Boundary

The project is intended for **personal use, college evaluation, and portfolio presentation**.

Implementation priorities:

1. Working core document-management functionality.
2. Simple and understandable architecture.
3. A consistent experience across web and desktop, with platform-specific capabilities.
4. Practical, basic security and account-level separation.
5. Cloud AI through OpenRouter as the implemented AI option.
6. Clear communication that Local AI is only a placeholder in the current version.
7. A useful user experience and a project that can be demonstrated reliably.

The project should not attempt to reproduce a government-scale digital document service or a bank-grade security platform. The central product is the **AI Digital Locker**; AI is a supporting feature.

## 32. Decisions Still Open

The following choices have not yet been finalized and should be clarified before their implementation:

- Whether the OpenRouter key is configured by the application owner on the backend or supplied individually by each user.
- Which OpenRouter model will be used.
- Whether Google Sheets reporting and the single-administrator functionality should both remain in the final scope.
- Any further account-registration limits appropriate for a project intended primarily for personal use.

Do not silently treat these open decisions as settled.
