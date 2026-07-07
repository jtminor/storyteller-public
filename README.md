# Storyteller

## What is the Storyteller Platform?

The Storyteller Platform is a new kind of CMS which we call a "generative streaming CMS". A traditional CMS is a database specialized to store and retreive content, usually html documents or other media. In a traditional CMS, content only exists if a user enters it. If content is requested and doesn't exist, an error or blank document is returned to the user.

The "generative" part of the generative streaming CMS changes that expectation, generating some minimally viable content for any valid content requests. This is made possible by the use of a semantic graph which defines the relationships between the content items and the context to generate the content whenever needed. In this system, the more content the user provides the better the other conetnt will become (a "content network effect"), but some content will always be avaliable even if the user hasn't input a single thing.

The "streaming" part reflects the different way content is delivered in the system. Rather than provide a synchronous complete document response when content is generated, the platform publishes sub-document level content, and pushes those content items to the client as Server Sent Events. These events include semantic content identifiers which identiy the pieces place in the content graph, allowing the system to continously deliver content in chunks via an asynchronous stream and the client to place those chunks based on their identity.

## Intro Demo

### Start Storyteller

After completing the Install and Setup steps, cd to the top level project directory and start the web server:

`flask run`

Confirm the server is running then open the Story Inspector by navigating to:
<http://127.0.0.1:5000/demo/inspect>

You should see the document instpector UI with options to Delete or Format a new document.

#### Create a New Document

In the Format Document panel, click Apply Format. This creates a new Story document in your Storyteller instance, formatted as a simple demo document about color. The inspector should load the visual representation of the document's Format (graph), as well as two tables: the Format Table and the Story Table.

#### Generate Coordinated Content

The demo document contains 4 pieces of content: a color, the color read aloud, an image of the color and a video combining these elements. The type and prompts for each of these pieces of content can be seen in the Fromat Table.

Click Generate on the demo.video row to start generating the document's conent.

Storyteller builds a semantic graph between the content based on their semantic dependency. So the audio of the color depends on the color's name being generated first. The video depends on all the other content existing, and so on. These relationships are shown visually on the graph.

#### Content States and Updates

By now the demo should have progressed to where content has been requested and received. The inspector interfaces uses animation and color to indicate the state of the document's content. For example content which has been successfully generated will become green.

The newly generated content can be seen in the Story table, which stores the actual "contents" of the document. First you should see the color name, then the audio and image, and finally the video. Click the preview button to open media urls.

#### Collaborating with Content Agents

Now lets change our initial color "by hand" and see the impact. Click on the text field in the Story Table containing the color name your model generated. Replace the color with "Aquamarine" and click Update.

As the content updates, the content which "depends" on the color value becomes "Inavlid", as it no longer coordinates correctly with Aquamarine. Click generate on the video row. The Invalid nodes are regenerated, with now correct values and the video will be recreated with all new content, automatically by the system traversing the semantic graph.

Each piece of Content in a Storyteller document is an Agent. It includes not just the content itself, but the prompts, model configurations, and memories of a unique LLM backed Agent. In combination with the semantic graph format system, this allows users and distributed agents to co-create documents and modify each others work.

To learn more please see the system documentation below.

## Setup and Installation

### Local Development Environment

These instructions will guide you through setting up and running Storyteller in a local development environment for Mac OS.

#### Prerequisite Installations

- Python: Download and install the latest version of Python from <https://www.python.org/downloads/> Ensure you select the option to add Python to your PATH during installation. It is strongly recommended that you do not use the default system installation and site packages.
- Google Cloud SDK: Download and install the Google Cloud SDK from <https://cloud.google.com/sdk/docs/install>. This will provide you with the gcloud command-line tool.
- VS Code: Download and install the latest version of Visual Studio Code from <https://code.visualstudio.com/> or load the project and configure your perferred IDE.

##### (Optional) VS Code Extensions

Open VS Code and navigate to the Extensions view (Ctrl+Shift+X or Cmd+Shift+X).
Search for and install the following extensions:

- Python
- Google Cloud Code

#### Create a Virtual Environment

1. Open a Terminal
2. Navigate to the root directory of your project.
3. Create a virtual environment using the following command:
 python -m venv .venv
Activate the virtual environment:
 source .venv/bin/activate

### Google Cloud Project Setup

1. In your Google Cloud Console, create a Cloud Run project to host your storyteller instance. You will also need to update the GC_PROJECT_ID constant in Storyteller.py with this new project name.
2. In your new project create a Firestore database and make it open to all users.
3. In the Firestore database create two Collections. Update the value of the STORY_COLLECTION_NAME and QUEUE_COLLECTION_NAME constants in Storyteller.py with these new collection names.
4. In the Cloud Console naviate to the Cloud Storage page and create two buckets, both open to all users. Update the values of the GCS_MEDIA_BUCKET_NAME and GCS_QUEUE_BUCKET_NAME constants in Storyteller.py with these new bucket names.

### Install the Google Cloud CLI

1. Install the Google Cloud CLI by following the instructions at <https://cloud.google.com/sdk/docs/install>
2. During install be sure to include gcloud in your shell PATH
3. CD to the storyteller project directory and configure the project with your instance name by running these two commands, replaceing YOUR_PROJECT_NAME with your Cloud Run project name:

`gcloud config project YOUR_PROJECT_NAME`

`gcloud auth application-default set-quota-project YOUR_PROJECT_NAME`

### Install Python Dependencies

Assuming you have Homebrew and PIP installed already, install the project dependencies from the requirements.txt file, if your IDE doesn't do so automatically:

`pip install -r requirements.txt`

### Install Ollama (Optional)

To run local models the platform uses the Ollama local web server. To install and set up Ollama see the github repo here: <https://github.com/ollama/ollama>

You can specfiy the OLLAMA_HOST and OLLAMA_PORT constants in Storyteller.py to use a LAN or other server.

## Starting a Local Storyteller Instance

- From the terminal, navigate to the main storyteller directory (ie. where runserver.py is located)
- Run the Flask web engine using the following command:

`flask run`

This will typically start the development server at <http://127.0.0.1:5000/>. You can access the application in your web browser or via http requests at this address.

## Web User Interfaces

### The API Test Client

Naviate to <http://127.0.0.1:5000/static/apitestclient.html> (or equivalent IP and port for your local environment).

This page includes full API documentation and a simple UI to test each API endpoint and view the response.

### The Story Inspector

Naviate to <http://127.0.0.1:5000/<document_name>/inspect> to open a full, live updating document inspector. This UI includes visualizations of the Format graph and complete access and control of the Conent of a Story document. It also live updates and animates the state of the Content Agents in the document.

## The REST API

### Checking Status Using the / "Home" Route

The / ("home") route of the API returns a version string, verifying the platform is live and reporting the active production build.

## API Usage Examples

1. **Start listening to a stream:**
   - **Request:** `GET /example_doc/streamcontent`
   - **Response:** An open stream connection. Content events will be pushed through this connection as they are generated.

2. **Index the content to see what is available:**
   - **Request:** `GET /example_doc/indexcontent`
   - **Response:** 
     ```json
    [
        {"id" : "test.id.1",
        "data": "A test key.",
        "type": "txt"
        },
        {"id": "test.id.2",
        "data": "Yet another test key.",
        "type": "txt"
        },
        {
        "id": "test.location",
        "data": "A test location.",
        "type": "loc"
        }  
       // ... more content items
    ]
     ```

3. **Ask to generate a piece of content:**
   - **Request:** `POST /example_doc/generatecontent`
     - **Body:** 
       ```json
       ["test.image"]
       ```
   - **Response:** 
     -  A `WAIT` event will be pushed to the stream.
     -  Once generated, a `REPLACE` event will be pushed to the stream with the image url:
       ```json
       {
         "type": "REPLACE",
         "content_id": "test.image",
         "data": "https://example.com/image.jpg" 
       }
       ```

4. **Change the value of that content:**
   - **Request:** `POST /example_doc/updatecontent`
     - **Body:**
       ```json
       {
         "content_id": "test.image",
         "data": "base64 image data" 
       }
       ```
   - **Response:** 
     - A `REPLACE` event will be pushed to the stream with the new images url.
       ```json
       {
         "type": "REPLACE",
         "content_id": "test.image,
         "data": "https://example.com/update_image.jpg" 
       }
       ``` 


## System Priciples

The system is designed to produce content following these key principles. If you want to know why something is the way it is, or what to do next, one of these should be the answer:

- Media Type Neutrality
- Deliver the Smallest Possible Piece of Content As Soon As Possible
- Expect Underspecified Context
- All Contents are Actually Agents

### System Benefits

Based on the architecture and principles of the system, it can offer the user and user interface a set of abilities that other approaches do not:

- Radical Editability - Every piece of content is individually editable by both human and agents
- Radical Interactivity - Every piece of content can be interacted with as an "intelligent" entity
- Content is A Stream - Content is pushed to the user interface in the smallest possible piece as soon as possible, making it maximally responsive to user input and requests.
- Semantic Anchors - Every piece of content has a shared defintion and relationships between them that all users can understand
- Creative Process - The process of creating content is modeled as a multiparticpant, multistep iteractive process, not a single command or chat interface
- Clear Collaboration - The shared content defintions and radical interactivity allow for very clear touch points and places for colloaboration between users, the user iterface, collaborator agents, and the content itself

## Core Concepts

**Document (aka Story)** - The core document stored and managed by the platform is called a Story. Story documents have two parts: a Format, which is a semantic graph which defines their contents, and Content, which are the actual contents the system or user has created.

**Content** - The core data encapsulation. Content represents part of a document, and includes the data for that part as well as a unique semantic content identifier, and type information.

**Format** - The schema which defines the Story's Content and the relationships between the Content, as well as default values, models to be used, etc.

**Agent** - Contents are Agents, in that they are backed by an AI model (or similar generative predictive system). Content is therefore interactive, or can be "talked to", and are stored and interacted with as Agents within the platform. Think of Content Agents as being content "brought to life", allowing users or other system components to interact with it in unqiue new ways.

**Publisher** - The part of the system which takes Content items and pushes them to clients as they are created or changed.

## Content

The Storyteller Platform utilizes a flexible and extensible idenitification system for managing content objects and their relationships using a meaningful idenifier, calles a "semantic" or Content Id.

### Content Objects

A content object represents a discrete piece of content within the document. Each content object is self-contained, meaning it can stand alone or be semantically linked to other content objects. This allows for a high degree of modularity and reusability. For example:

- A content object could be a single sentence, a paragraph, an image, a video clip, or a geolocation tag. 
- These objects can be assembled, rearranged, and modified independently, providing a dynamic and flexible approach to content creation.

### Semantic Content IDs

Every content object is assigned a unique semantic ID. This ID is not a simple database key, but rather a meaningful identifier that reflects the content's purpose. This semantic approach to identification enables:

- **Intelligent Linking:**  Content objects can be automatically connected based on their semantic relationships, facilitating the discovery of related content.
- **Contextual Understanding:** The system can interpret the meaning and relevance of content objects based on their IDs, leading to more intelligent content generation and assembly.

Semantic ids contain only alphanumeric characters, and use dot notation to signify nesting or hierarchy. For example: "test" is the key for all test content, and "test.image" is the key for the test image that is part of the test content set. 

Content ids created for system intenal metadata begin with _ (underscore) and do not use dot notation nesting. These content items are not tied to the Format and are not intended for client or end user use.

### Content Types

The Storyteller Platform supports a variety of content types, ensuring versatility in content creation and presentation. These types include:

- **txt:** Represents textual content, such as sentences, paragraphs, or entire articles.
- **img:** Denotes image-based content, allowing for the incorporation of visual elements.
- **video:** Represents video content, enabling the inclusion of dynamic and engaging multimedia.
- **audio:** Represents audio content, providing a means to incorporate sound and spoken word.
- **loc:** Represents location data, enabling location-based content and experiences.
- **set:** Represents a collection of content objects, allowing for the grouping and organization of related content.
- **sys:** System internal metacontent, not meant for end user diplay or editing. Content ids for sys contnet start with "_".

### The Content Index

The Content Index serves as a comprehensive listing for all content objects in a Story. The Content Index includes all the potential conent ids a document can generate, a short human readable description of the content, and its media type.

## Content Events

Content Events are the primary mechanism for communication between the Storyteller Platform and a user interface. They provide a real-time, asynchronous stream of information about changes and updates to the content being generated. This event-driven architecture allows for a highly dynamic and responsive user experience.

### The Content Event Stream

The Content Event Stream is a continuous flow of Content Events, broadcast by the Storyteller to any connected clients, such as a web browser, sms bridge, or native application.  This stream acts as a live feed, delivering updates as they occur.

### Content Event Properties

A Content Event represents a specific action or change related to a content object. Each event carries information about:

- **Event Type:**  The nature of the change (e.g., content replacement, addition, new content generation).
- **Content ID:** The semantic ID of the content object affected by the event.
- **Content Data:** The actual content data associated with the event, if applicable.

### Content Event Types

The Storyteller Platform defines several Content Event Types to represent different scenarios:

- **REPLACE:**  Signals that existing content with the specified ID should be replaced with the provided content data.
- **ADD:** Indicates that the provided content data should be added to any existing content with that id.
- **NEW:**  Announces the generation of new content in a content set. The event will include the newly created Content ID and data.
- **ERROR:**  Communicates an error encountered during content generation or processing. The event data will contain an error message.
- **WAIT:**  Indicates that the system has no content to deliver at this time, but may in the future, and includes a time in milliseconds the client should expect to wait, *at a minimum* before any additional events will be sent.
- **END:**  Signals the completion of a content generation cycle or closing of the stream. The client should expect no further events from this stream.
- **RESATE:** The content has changed state. The data value will contain the new state.

## The Publisher

The Publisher is a core component of the Storyteller Platform responsible for managing the flow of Content Events from the system to the user interface. It acts as an intermediary, buffering content, converting it into events, and broadcasting those events to connected clients.

### The Buffer

The Publisher utilizes a buffer to handle the asynchronous nature of content generation and stateless server communication. As content objects are created or modified, they are not immediately sent to the client. Instead, they are placed in the Publisher's buffer. The Publisher then delivers those stored content objects using the EventStream standard. 

### Converting Content to Content Events

When the Publisher is ready to send content to the client, it converts the buffered content objects into Content Events. This conversion process involves:

- **Wrapping Content Data:**  The content object's data is packaged into the event's payload.
- **Assigning Event Types:** The appropriate Content Event Type (REPLACE, ADD, NEW, etc.) is assigned based on the context of the content change.

### Listening to Content Events

The Publisher provides a mechanism for clients to subscribe to the Content Event Stream. When a client calls streamcontent a EventStream object is returned to which conent events will be pushed.

## Document Format

The Format defines the structure and content that can be generated for a document within the Storyteller Platform. It acts as a blueprint, outlining the possible content elements, their relationships, media types and the prompts and models used to generate them.

### A Semantic Graph for Content Generation

The Document Format is structured as a semantic graph, where each node represents a content item and the edges represent relationships or dependencies between them. This graph-based approach enables:

- **Content Referencing:** Content prompts can refer to other content items within the graph, allowing for the creation of interconnected and contextually relevant content. For example, a prompt for generating an image caption can reference the previously generated image content.
- **Dynamic Content Flow:** The generation process can follow the relationships defined in the graph, ensuring that content is created in a logical and coherent order.
- **Content Reusability:**  Common content elements or structures can be defined once and reused across multiple document types, promoting consistency and efficiency.

### The Format JSON Schema

The Document Format is represented using a JSON schema document. This schema defines the structure of the graph, the types of content nodes, and the properties associated with each node.

Here's a schema of the Format JSON defintion syntax:

```json
{
    "DISPLAY_NAME": "Format Name",
    "DESC": "A short description of the document format",
    "AGENTS": {
        "<content id>": {
            "DESC":"A short description of the content",
            "DATA": "default content",
            "TYPE": "<media type:txt,img,video,audio,set,loc>",
            "STATE": "<generation state:needed,active,done,locked>",
            "SYSTEM": "optional system prompt",
            "PROMPTS": ["a prompt string with a §content.id§ replacement variables"],
            "MEMORIES": ["a memory string"]
        }
    }
}
```

## Agents

In the Storyteller Platform, content generation is driven by a network of intelligent agents. Each content item within a document is associated with a dedicated Content Agent. These agents are responsible for managing the generation of their content, storing memories and deirectives, and interaction with other agents or users.

### Content Agents

A Content Agent encapsulates the following that enables a piece of Content to act as an Agent:

- **Content ID:**  A unique semantic ID that identifies the content item the agent is responsible for.
- **Content Data:** The actual content data (text, image URL, etc.) associated with the content item.
- **Generation State:**  Indicates the current status of the content generation process (more on this below).
- **Prompts:** A list of prompt strings that can be used to generate the content. These prompts can include variables that reference other content items in the document.
- **Memories:** A collection of previously generated content or sytem directives that can be used as context for future generation.
- **Semantic Dependencies:** The other content agents this content uses as context for its generation.

### The Agent Store

The Agent Store is a central registry that manages all Content Agents within a document. It provides mechanisms for:

- **Agent Creation:** Creating new agents for each content item defined in the Document Format.
- **Agent Retrieval:**  Retrieving agents based on their Content IDs.
- **State Management:**  Updating the generation state of agents as content is generated or modified.

### Agent States

Content Agents can be in one of several states, reflecting their progress in the content generation process:

- **needed:** The content item is required but has not yet been generated.
- **generating:** The agent is actively in the process of generating content.
- **invalid:** The agent's current state is out of sync with its dependencies, and should not be trusted.
- **done:** The content has been successfully generated and is ready for use.
- **locked:** The content is considered final and can not be regenerated.

Changes in agent state are published as RESTATE event types.

### System Prompts

For sevices and models that support the concept of a System prompt, an agent may specfiy a System value. This string will be used as the system prompt if the Model supports it. Otherwise it will be appended as the first message passed to the model as a normal prompt.

### Prompts and Content Variables

Each Content Agent has a list of associated prompts. These prompts are instructions or templates that guide the content generation process. Prompts can include variables that reference other content items in the document, allowing for the creation of interconnected and contextually relevant content.

For example, a prompt for generating an image caption might look like this:
`Write a short caption for this image: §user.image§.`

The variable `§user.image§` would be replaced with image data stored with the semantic id `user.image`, if it exists.

### Memories

Content Agents can store memories, which are pieces of information that can be used as context for future content generation. Memories can include:

- Previously generated content for the same content item.
- User feedback or edits.
- Relevant information retrieved from external sources.

By leveraging memories, Content Agents can improve the relevance and coherence of the generated content over time.

### Messages

Content Agents communicate with each other and with external services through messages. Messages can be used to:

- **Request content generation:** An agent can send a message to another agent requesting the generation of specific content.
- **Share information:** Agents can share memories or other relevant data with each other.

There are two primary ways agents communicate with each other, both cases using Messages:

- **Tell:** One agent Tell a message another agent, to provide information to that agent. This information will become a memory for the receiving agent.
- **Ask:** An agent can Ask another agent a message. This request is then tranformed by the receiving agent into a response which is returned to the sending agent.

## Models

The system performs all Agent actions, including initial content generation, using a set of Models accessed via the ModelInterface class. The service and model used by an Agent as well as the parameters to pass to that model are defined by a Model Configuration. Agents may define specify a MODEL value in their format which will override the default model and use the ModelConfiguration named in the value.

### Supported Model Services

Currently the platform supports Google Vertex, OpenAI and Ollama out of the box, along with a unit Test model option. Additional services can be accessed via Google's Model Garden or by implementing generation functions for the serivce in the Model Interface.

### Model Configuration

Model Configurations define the basic context for a generation reqeust. In addition to the service name, model name and model secret (if neededd), a configuration may include a paramters dictionary. This dictionary can be used to pass arbitary or model specific parameters as part of a generation request. For example, an image ModelConfiguration may include the size or quality settings for a specific model's api.

### Adding or Editing Model Configurations

Model Configurations are defined as JSON objects in the model_configs.json file which is stored in the /main directory with the core code. Model Configuration objects must include a service name, model name and model secret, even if those values are empty strings.

To add a new model configuration for an existing service, create a new Configuration object and copy the existing Configuration for the service name and secret, and change the model name to your target model. You may also need to add or edit paramters.

### Service Authorization, API Keys and Secrets

Serivces, such as OpenAI that require API keys, identfiers or other secrets for requests are authenticated by looking up the secret name defined in the Configuration in the .env. That is, in the Model Configuration the model_secret refers to the environemntal variable name which holds the actual secret, API KEYS AND SECRETS SHOULD NOT BE DIRECTLY INCLUDED in the Configuration. Include them in your environemnt and use the configuration to point to the needed environmental variable.

### The Default Gemini Interface

In the current platform, the system uses the Gemeni and Vertex AI services by default. This is defined in the DEFAULT_MODEL_CONFIG value.

## Media Storage

The Storyteller Platform utilizes Google Cloud Storage (GCS) for storing uploaded and generated media files.

### Media Content Data is a URL, Not Raw Data

Within the Storyteller Platform, media content is represented as URLs pointing to the corresponding objects stored in Google Cloud Storage.

### Storage and URL Generation for Media Types

When a user uploads media or a transformer creates media the following process occurs:

1. **Upload to GCS:** The media file is uploaded to a designated GCS bucket.
2. **URL Generation:**  GCS automatically generates a unique and publicly accessible URL for the uploaded object.
3. **URL Storage:** The generated URL is published and stored as the content data for the corresponding content item within the Storyteller document.

## Error Handling

### Content Generation related Errors are Published as Error Events

In addition to the usual logging and http response codes, where appropriate, the system also publishes errors as Content Events. These Error events often contain more details about the failure. Clients should listen for errors in the Content Stream and deal with them (ie. present them to the user, retry, etc) in addition to standard http response errors.

## Epigraph

> The storyteller makes no choice<br>
> Soon you will not hear his voice<br>
> His job is to shed light<br>
> And not to master<br>
><br>
> Since the end is never told<br>
> We pay the teller off in gold<br>
> In hopes he will come back<br>
> But he cannot be bought or sold<br>
><br>
> Robert Hunter - Terrapin Station<br>
