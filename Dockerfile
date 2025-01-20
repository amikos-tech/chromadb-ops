FROM chromadb/chroma:latest as base

COPY ./ /chroma_ops

WORKDIR /chroma_ops

# install poetry
RUN pip install poetry && \
    poetry lock && \
    poetry install --no-interaction --no-ansi

ENTRYPOINT ["poetry", "run","chops"]
