"""Assign dummy credentials before test modules import main.
Assignments override shell values so real credentials cannot enter route tests.
"""

import os

os.environ["SUPABASE_URL"] = "http://supabase.invalid"
os.environ["SUPABASE_KEY"] = "fake-supabase-key-for-tests"
os.environ["OPENAI_API_KEY"] = "fake-openai-key-for-tests"
