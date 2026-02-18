# EVA Assistant
Local chatbot powered by Deepseek AI model.

## Prerequisites
* Python 3.8+
* pip (Python package installer)
* Ollama with Deepseek installed locally

## Usage

This project runs through a venv virtual environment in order to keep dependencies from interfering with other local projects.

First, you will need to ensure you load into the virtual environment before installing packages.

For Linux:
```
$ source EVA_Assistant/bin/activate
$ pip install flask
```

For Windows:
```
$ EVA_Assistant\Scripts\activate
$ pip install flask
```

The chat interface currently runs on a local Flask server. To start the server, run in the terminal:
```
$ python3 app.py
```
The Flask server will start at http://127.0.0.1:5000/

## Future Updates
* Create backend functionality to store and use conversation history for more in-context responses.
* Optimize model reponse behavior with different prompt designs and Ollama CLI parameters.
* Create a more solidified environment for the chatbot.
