# EDBA - Organization Management System

```text
███████╗██████╗ ██████╗  █████╗
██╔════╝██╔══██╗██╔══██╗██╔══██╗
█████╗  ██║  ██║██████╔╝███████║
██╔══╝  ██║  ██║██╔══██╗██╔══██║
███████╗██████╔╝██████╔╝██║  ██║
╚══════╝╚═════╝ ╚═════╝ ╚═╝  ╚═╝
```

A Flask-based organization management system for managing members, services, and applications.

> **Note**: This project was developed in early 2025 as a group assignment for the **Advanced Software Development Workshop** course during my junior year (Year 3) of undergraduate studies. It was built by a team of students as a course project and is not intended for production use. The codebase reflects the learning process and time constraints of a university course project.


## Features

- **🔐 Advanced Authentication**: Email verification code system with session-based security
- **👥 Multi-Role Architecture**: Granular access control (OC, TT, EE, SE, PP, PC, CC)
- **🏢 Organization Management**: Full CRUD operations for organizational entities
- **⚙️ Service Configuration Engine**: Dynamic management of enterprise services
- **📋 Intelligent Application Workflow**: O-Convener registration pipeline
- **📜 Policy Management System**: Centralized organizational policy engine

## User Role Matrix

### **Admin Tier**
| Role | Title                        | Privilege Level |
|------|------------------------------|-----------------|
| **OC** | O-Convener                   | Highest        |
| **TT** | Thesis Administrator         | High           |
| **EE** | Executive Administrator      | High           |
| **SE** | Senior Executive Administrator | Elevated     |

### **Operational Tier**
| Role | Title                        | Access Type     |
|------|------------------------------|-----------------|
| **PP** | Data Provider                | Write          |
| **PC** | Public Data Consumer         | Read (Public)  |
| **CC** | Private Data Consumer        | Read (Restricted) |

## Service Ecosystem

| Code | Service                    | Description                     |
|------|---------------------------|---------------------------------|
| **S** | Thesis Search             | Intelligent document retrieval |
| **P** | PDF Download              | Secure document distribution   |
| **C** | Course Information        | Academic data hub              |
| **A** | Student Authentication    | Identity verification          |
| **R** | GPA & Academic Records    | Performance analytics          |
| **M** | Money Transfer            | Financial transaction gateway  |

---

## Quick Start

### Prerequisites
- **Python 3.8+**
- **pip** package manager

### Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd src

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd src
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create environment configuration:
```bash
cp .env.example .env
```

5. Edit `.env` with your configuration:
```
SECRET_KEY=your-secret-key-here
MAIL_SERVER=smtp.example.com
MAIL_PORT=465
MAIL_USERNAME=your-email@example.com
MAIL_PASSWORD=your-email-password
```

6. Initialize the database:
```bash
python init_db.py
```

7. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Configuration

Environment variables can be set in the `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| SECRET_KEY | Flask secret key | dev-secret-key-change-in-production |
| DATABASE_URL | Database connection URL | sqlite:///instance/EDBA.db |
| MAIL_SERVER | SMTP server address | smtp.example.com |
| MAIL_PORT | SMTP server port | 465 |
| MAIL_USE_SSL | Use SSL for mail | True |
| MAIL_USE_TLS | Use TLS for mail | False |
| MAIL_USERNAME | Email account username | - |
| MAIL_PASSWORD | Email account password | - |
| DEBUG | Debug mode | True |

## Project Structure

```
src/
├── app.py              # Main application entry point
├── config.py           # Configuration settings
├── models.py           # Database models
├── db_manager.py       # Database management utility
├── db_utils.py         # Database utility functions
├── requirements.txt    # Python dependencies
├── .env.example        # Environment configuration template
├── auth/               # Authentication module
├── admin/              # Admin module
├── user/               # User module
├── oconvener/          # O-Convener module
├── templates/          # HTML templates
├── static/             # Static files (CSS, JS, images)
├── instance/           # Database and uploaded files
└── migrations/         # Database migration scripts
```

## Database Management

Use the database manager utility:

```bash
python db_manager.py
```

Available operations:
1. View table
2. Add record
3. Update record
4. Delete record
5. Recreate database
6. Reset database (preserve specific records)
7. Export members table to Excel
8. Exit

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Known Limitations & Shortcomings

As a university course project developed under time constraints, this system has several notable limitations:

### Security
- **Session-based authentication without proper token management**: The system uses Flask sessions for authentication, which is not ideal for distributed systems. No JWT or OAuth2 implementation.
- **No rate limiting on API endpoints**: Vulnerable to brute-force attacks on login and verification code endpoints.
- **No CSRF protection**: Missing CSRF tokens on forms, making the application vulnerable to cross-site request forgery attacks.
- **No input sanitization on some endpoints**: Potential risk of SQL injection or XSS in certain areas.
- **Verification codes stored in session**: Not scalable and can be bypassed if session handling is compromised.

### Architecture & Code Quality
- **No REST API design**: The application uses traditional server-side rendering with Flask templates rather than a decoupled frontend/backend architecture.
- **No unit tests**: The project lacks a comprehensive test suite, making it difficult to ensure correctness when making changes.
- **Tight coupling**: Business logic is mixed with route handlers in view files, violating the separation of concerns principle. No service layer or repository pattern is used.
- **No proper error handling**: Many endpoints lack graceful error handling, and error messages may expose internal details.
- **Hardcoded values in some places**: Despite refactoring, some configuration values and magic numbers remain in the code.
- **No database migration tool**: Uses raw SQL migration scripts instead of a proper migration tool like Flask-Migrate/Alembic.

### Functionality
- **No password-based authentication**: Relies entirely on email verification codes, which depends on a working mail server and is inconvenient for users.
- **No real-time notifications**: Users must manually check for application status updates.
- **Limited audit logging**: System logs are basic and lack detailed activity tracking.
- **No pagination**: Lists and tables load all records at once, which will cause performance issues with large datasets.
- **No file upload validation**: Limited validation on uploaded file types and content.
- **No multi-language support**: The UI mixes Chinese and English inconsistently.

### UI/UX
- **No responsive design**: The frontend templates are not optimized for mobile devices.
- **No frontend framework**: Uses plain HTML templates with minimal JavaScript, resulting in a dated user experience.
- **Inconsistent styling**: UI styling varies across different pages and modules.

## Future Work

If this project were to be continued or improved, the following areas should be addressed:

### High Priority
- [ ] **Implement proper authentication**: Add password-based authentication with bcrypt hashing, or integrate OAuth2/OIDC for SSO.
- [ ] **Add comprehensive test suite**: Write unit tests and integration tests using pytest.
- [ ] **Implement CSRF protection**: Add Flask-WTF or similar for CSRF token management.
- [ ] **Add rate limiting**: Implement rate limiting on authentication endpoints using Flask-Limiter.
- [ ] **Decouple frontend and backend**: Build a REST API backend and a modern SPA frontend (React/Vue).

### Medium Priority
- [ ] **Refactor with service layer**: Separate business logic from route handlers using a service/repository pattern.
- [ ] **Add Flask-Migrate**: Replace raw SQL migration scripts with Alembic-based migrations.
- [ ] **Implement pagination**: Add pagination for all list views.
- [ ] **Add real-time notifications**: Use WebSocket (Flask-SocketIO) for real-time updates.
- [ ] **Improve file upload security**: Add proper file type validation, virus scanning, and size limits.
- [ ] **Add API documentation**: Use Swagger/OpenAPI to document API endpoints.

### Low Priority
- [ ] **Responsive design**: Make the UI mobile-friendly using a CSS framework like Bootstrap or Tailwind.
- [ ] **Internationalization (i18n)**: Add proper multi-language support using Flask-Babel.
- [ ] **Docker deployment**: Add Dockerfile and docker-compose for easy deployment.
- [ ] **CI/CD pipeline**: Set up GitHub Actions for automated testing and deployment.
- [ ] **Monitoring and alerting**: Add application monitoring with tools like Sentry or Prometheus.

## Security Notes

- Never commit the `.env` file with real credentials
- Change the default `SECRET_KEY` in production
- Use strong passwords for email accounts
- Keep the database file (`instance/EDBA.db`) secure
