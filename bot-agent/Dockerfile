FROM python:latest

RUN apt update

RUN apt -y install telnet iputils-ping

RUN useradd -ms /bin/bash bot-agent

RUN mkdir sudo /opt/bot-agent

RUN chown -R bot-agent:bot-agent /opt/bot-agent

USER bot-agent

WORKDIR /opt/bot-agent

COPY . .
CMD ["/usr/local/bin/python", "bot-agent.py"]
