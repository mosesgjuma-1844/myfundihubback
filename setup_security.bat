@echo off
REM Security Setup Script for FUNDI Backend (Windows)

echo.
echo 🔐 FUNDI Backend Security Setup
echo ================================
echo.

REM Step 1: Install dependencies
echo 📦 Step 1: Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Failed to install dependencies
    exit /b 1
)
echo ✅ Dependencies installed successfully
echo.

REM Step 2: Run migrations
echo 🗄️  Step 2: Running database migrations...
python manage.py makemigrations api
if errorlevel 1 (
    echo ❌ Failed to create migrations
    exit /b 1
)
echo ✅ Migrations created

python manage.py migrate
if errorlevel 1 (
    echo ❌ Failed to migrate database
    exit /b 1
)
echo ✅ Database migrated successfully
echo.

REM Step 3: Set environment variables information
echo 🔑 Step 3: Environment Variables Setup
echo Run the following commands in your terminal:
echo.
echo set ADMIN_REGISTRATION_KEY=your-secure-admin-key-here
echo set DEBUG=False
echo.
echo Or add to your .env file (don't commit to version control)
echo.

REM Step 4: Collect static files
echo 📁 Step 4: Collecting static files...
python manage.py collectstatic --noinput
if errorlevel 1 (
    echo ⚠️  Warning: Failed to collect static files (may not be critical)
) else (
    echo ✅ Static files collected
)
echo.

echo ✅ Security setup complete!
echo.
echo 📚 Documentation: See SECURITY_IMPROVEMENTS.md for details
echo 🧪 Testing: Run 'python manage.py test' to verify
echo.
pause
