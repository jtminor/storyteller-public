# Storyteller (Public Version)

## What is the Storyteller Platform? 
The Storyteller Platform is a new kind of CMS which we call an Agentic Streaming Content Manamement System". 


 generating some minimally viable content for any valid content requests. This is made possible by the use of a semantic graph which defines the relationships between the content items and the context to generate the content whenever needed. In this system, the more content the user provides the better the other conetnt will become (a "content network effect")

The "streaming" part reflects the different way content is delivered in the system. Rather than provide a synchronous complete document response when content is generated, the platform publishes sub-document level content, and pushes those content items to the client as Server Sent Events. These events include semantic content identifiers which identiy the pieces place in the content graph, allowing the system to continously deliver content as is generated or modified.

## Quick Demo

Color example using inspector (screenshots)

### Key terms: document, format, content
#### Create a document (load the inspector)
#### Format a document (index) 
#### Creating content (generate)
#### Combining content (prompt variables and videos)
#### Editing content (set)
#### Rebuilding content after editing (states and dependency)

## The Inspector Web UI
You can use the /{doc_id}/inspect endpoint to view the Format and Story for a document and generate, update and stream all content items and events for the document.

### Inspector intros/howto (create, index, generate, update, status)

## More Content Creation Examples
### Custom Tarot Deck and Reading
### Basketball Promo Video
### Your Personal Odyssey

## The REST API

### The API Test Client
Naviate to http://127.0.0.1:5000/static/apitestclient.html (or equivalent IP and port for your local environment). 

This page includes full API documentation and a simple UI to test each API endpoint and view the response.

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

## Product Benefits
Based on the architecture and principles of the system, it can offer the user and user interface a set of abilities that other approaches do not:
- Radical Editability - Every piece of content is individually editable by both human and agents
- Radical Interactivity - Every piece of content can be interacted with as an "intelligent" entity
- Content is A Stream - Content is pushed to the user interface in the smallest possible piece as soon as possible, making it maximally responsive to user input and requests.
- Semantic Anchors - Every piece of content has a shared defintion and relationships between them that all users can understand
- Creative Process - The process of creating content is modeled as a multiparticpant, multistep iteractive process, not a single command or chat interface
- Clear Collaboration - The shared content defintions and radical interactivity allow for very clear touch points and places for colloaboration between users, the user iterface, collaborator agents, and the content itself

## Core Concepts
Documents (aka Stories) - The document is called a Story, that the user is interacting with. Documents have a Format, which is the graph to define their contents, and then Content items which are the actual content the system or user has created. You can think of this like the html doc in a web system, and the Format is the standard the documents markup conforms to.

Content - The core data encapsulation. Content represents part of a document, and includes the data for that part as well as meta information about the data: its "semantic" or content identifier, and its media type. Think of these as elemnents in a DOM.

Format - The schema which defines the Story's Content and the relationships between the content, as well as default values, etc. 

Agents - Content items are agents, in that they are backed by an AI model (or similar generative predictive system). Content is therefore interactive, or can be "talked to", and this ability is respresented by Agents in the system. Think of Agents as being content "brought to life", allowing users or other system components to interact with it in unqiue new ways.

Publisher - The part of the system which takes Content items and pushes them to clients as they are created or changed. 

## Content Objects and Ids 

The Storyteller Platform utilizes a flexible and extensible idenitification system for managing content objects and their relationships using a meaningful idenifier, calles a "semantic" or Content Id.

### Content Objects

A content object represents a discrete piece of content within the document. Each content object is self-contained, meaning it can stand alone or be semantically linked to other content objects. This allows for a high degree of modularity and reusability. For example:

- A content object could be a single sentence, a paragraph, an image, a video clip, or a geolocation tag. 
- These objects can be assembled, rearranged, and modified independently, providing a dynamic and flexible approach to content creation.

### Semantic IDs

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

### Content Events

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

## Formats (Content Schema)

The Format defines the structure and content that can be generated for a specific type of document within the Storyteller Platform. It acts as a blueprint, outlining the possible content elements, their relationships, and the prompts used to generate them.

### A Semantic Graph for Content Generation

The Document Format is structured as a semantic graph, where each node represents a content item and the edges represent relationships or dependencies between them. This graph-based approach enables:

- **Content Referencing:** Content prompts can refer to other content items within the graph, allowing for the creation of interconnected and contextually relevant content. For example, a prompt for generating an image caption can reference the previously generated image content.
- **Dynamic Content Flow:** The generation process can follow the relationships defined in the graph, ensuring that content is created in a logical and coherent order.
- **Content Reusability:**  Common content elements or structures can be defined once and reused across multiple document types, promoting consistency and efficiency.

### The Format JSON Schema

The Document Format is represented using a JSON schema document. This schema defines the structure of the graph, the types of content nodes, and the properties associated with each node. 

Here's a meta example of the Format JSON schema:

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

## Models, Model Interface and Model Configurations
The system performs all Agent actions, including initial content generation, using a set of Models accessed via the ModelInterface class. The service and model used by an Agent as well as the parameters to pass to that model are defined by a Model Configuration. Agents may define specify a MODEL value in their format which will override the default model and use the ModelConfiguration named in the value.

### Supported Model Services
Currently the platform supports Google Vertex, OpenAI and Ollama (local) out of the box, along with the Test model option. Additional services can be accessed via Google's Model Garden or by implementing generation functions for the serivce in the Model Interface.

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
