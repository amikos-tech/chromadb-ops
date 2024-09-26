try:
    import chromadb  # noqa: F401
except ImportError:
    raise ValueError(
        "The chromadb is not installed. This package (chromadbx) requires that Chroma is installed to work. "
        "Please install it with `pip install chromadb`"
    )
