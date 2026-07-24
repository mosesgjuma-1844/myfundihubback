#!/bin/bash
# Security Setup Script for FUNDI Backend

echo "🔐 FUNDI Backend Security Setup"
echo "================================"
echo ""

# Step 1: Install dependencies
echo "📦 Step 1: Installing dependencies..."
pip install -r requirements.txt
if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo ""

# Step 2: Run migrations
echo "🗄️  Step 2: Running database migrations..."
python manage.py makemigrations api
if [ $? -eq 0 ]; then
    echo "✅ Migrations created"
else
    echo "❌ Failed to create migrations"
    exit 1
fi

python manage.py migrate
if [ $? -eq 0 ]; then
    echo "✅ Database migrated successfully"
else
    echo "❌ Failed to migrate database"
    exit 1
fi
echo ""

# Step 3: Set environment variables (for local development)
echo "🔑 Step 3: Environment Variables Setup"
echo "Run the following commands in your terminal:"
echo ""
echo "export ADMIN_REGISTRATION_KEY='your-secure-admin-key-here'"
echo "export DEBUG='False'"
echo ""
echo "Or add to your .env file (don't commit to version control)"
echo ""

# Step 4: Collect static files
echo "📁 Step 4: Collecting static files..."
python manage.py collectstatic --noinput
if [ $? -eq 0 ]; then
    echo "✅ Static files collected"
else
    echo "⚠️  Warning: Failed to collect static files (may not be critical)"
fi
echo ""

echo "✅ Security setup complete!"
echo ""
echo "📚 Documentation: See SECURITY_IMPROVEMENTS.md for details"
echo "🧪 Testing: Run 'python manage.py test' to verify"
echo ""
