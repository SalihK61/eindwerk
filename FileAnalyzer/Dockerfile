FROM python:3.11-slim as builder
WORKDIR /app
COPY ./FileAnalyzer/requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY FileAnalyzer/ .
# tell Render which port your app listens on
ENV PORT=4000
EXPOSE 4000

# use shell form so $PORT is interpolated
CMD sh -c "gunicorn --bind 0.0.0.0:\$PORT app:app"
