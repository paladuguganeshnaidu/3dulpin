"""ML package: assistive models + heuristics (optional at runtime).

Core principle: GIS/database is the source of truth. ML here only produces
*assistive* candidates that are explicitly labelled AI-derived and require
human verification. Heavy models are NOT downloaded at startup; they are
loaded lazily and only when enabled.
"""
