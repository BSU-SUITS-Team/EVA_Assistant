# EVA Assistant
Local chatbot powered by Ollama.

## Prerequisites
* Python 3.8+
* pip (Python package installer)

## Dependencies
* Ollama
  * Stored locally on machine to run chatbot
* LangChain
  * Open-source framework with pre-built agent architecture and integrations
* Chroma
  * Vector store database
* Pandas
  * Library to read in files

## Usage

This project runs through a venv virtual environment in order to keep dependencies from interfering with other local projects.

### Python Setup/Installation
In the command terminal, you will need to load into the virtual environment first, before installing packages. To do this:

Linux/MAC:
```console
$ ./venv/bin/activate
$ pip install -r ./requirements.txt
```

Windows:
```console
$ ./venv/Scripts/activate
$ pip install -r ./requirements.txt
```
After running this, the required dependencies will be installed into the virtual environment to use.

### Ollama Setup
Next, to be able to locally run a model, you will need to download [Ollama](https://ollama.com/) from their website. 
This EVA assitant uses the llama3.2 model, as well as an embedding model mxbai-embed-large. We will download these from the console using the ollama command.

```console
$ ollama pull llama3.2
pulling manifest
...
success
$ ollama pull mxbai-embed-large
pulling manifest
...
success
```
### Starting Chat (currently in terminal)
To run the chat in the terminal:

Linx/MAC:
```console
$ python3 main.py
```
Windows:
```console
$ python main.py
```

## Needed Information/Discussion Topics
* Understanding the way the chatbot can reference mission information to create the proper output
* 

## Future Updates
* Create backend functionality to store and use conversation history for more in-context responses.
* Optimize model reponse behavior with different prompt designs and Ollama CLI parameters.
* Create a more solidified environment for the chatbot.
