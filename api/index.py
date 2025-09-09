from ytanalyzer.webapp.app import create_app

# Vercel Python Serverless Function entrypoint
# Exposes a WSGI app named `app`
app = create_app()

