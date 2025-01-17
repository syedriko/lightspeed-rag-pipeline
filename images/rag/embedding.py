__import__('pysqlite3')

import json
import sys
import os
import time
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

from llama_index import VectorStoreIndex, SimpleDirectoryReader, ServiceContext
from llama_index.vector_stores import ChromaVectorStore
from llama_index.storage.storage_context import StorageContext

import argparse
import asyncio

# Constant
PRODUCT_INDEX = "product"

def load_docs(folder): 
    # get files 
    file_paths = []
    for folder_name, _, files in os.walk(folder):
        for file in files:
            # Create the full path by joining folder path, folder name, and file name
            file_path = os.path.join(folder_name, file)
            file_paths.append(file_path)
    print(f"** Found {len(file_paths)} files ")
    return file_paths   

def get_eval_results(key, eval_results):
    results = eval_results[key]
    correct = 0
    for result in results:
        if result.passing:
            correct += 1
    score = correct / len(results)
    print(f"{key} Score: {score}")
    return score


async def main(): 
    
    start_time = time.time()
    # collect args 
    parser = argparse.ArgumentParser(
        description="embedding cli for task execution"
    )
    parser.add_argument("-t", "--vector-type",   default="local", help="Type of vector db[local,chromadb,chromadb-local, milvus]")
    parser.add_argument("-u", "--url", help="VectorDB URL")    
    parser.add_argument("-p", "--port", help="VectorDB port")    
    parser.add_argument("-a", "--auth", help="Authentication headers per vectorDB requirements")    
    parser.add_argument("-n", "--collection-name", help="Collection name in vector DB")
    parser.add_argument("-f", "--folder", help="Plain text folder path")
    parser.add_argument("-m", "--model",   default="local:BAAI/bge-base-en", help="LLM model used for embeddings [local,llama2, or any other supported by llama_index]")
    parser.add_argument("-e", "--include-evaluation",   default="True", help="preform evaluation [True/False]")
    parser.add_argument("-q", "--question-folder",   default="", help="docs folder for questions gen")
    parser.add_argument("-c", "--chunk",   default="1500", help="chunk size for embedding")
    parser.add_argument("-l", "--overlap",   default="10", help="chunk overlap for embedding")
    parser.add_argument("-o", "--output", help="persist folder")


    # execute 
    args = parser.parse_args() 
    
    PERSIST_FOLDER = args.output
    CHUNK_SIZE=int(args.chunk)
    CHUNK_OVERLAP=int(args.overlap)
    
    # setup storage context 
    if args.vector_type == "local": 
        print("** Local embeddings ") 
        storage_context = StorageContext.from_defaults()
        
    elif args.vector_type == "chromadb":
        print("** chromadb embeddings ")
        #Validate Inputs 
        if args.url is None or args.port is None: 
            print(" Missing URL or PORT ")
            return 
        
        chroma_client = chroma.HttpClient(host=args.url, port=args.port, headers=json.loads(args.auth) )
        collection = chroma_client.create_collection(
            name=args.collection_name,
            get_or_create = True            
            )
        vector_store = ChromaVectorStore(chroma_collection=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        
    elif args.vector_type == "chromadb-local":
        chroma_client = chromadb.Client()
        collection = chroma_client.create_collection(
            name=args.collection_name,
            get_or_create = True            
            )
        vector_store = ChromaVectorStore(chroma_collection=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store )
    
        
    elif args.vector_type == "milvus":
        return 
    
    print("** Configured storage context")
    
    service_context = ServiceContext.from_defaults(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,embed_model=args.model, llm='local')
    print("** Configured service_context")
    
    documents = SimpleDirectoryReader(input_files=load_docs(args.folder)).load_data()
    print("** Loading docs ")

    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context, service_context=service_context, show_progress=True
    )
    index.set_index_id(PRODUCT_INDEX)
    index.storage_context.persist(persist_dir=PERSIST_FOLDER)
    print("*** Completed  embeddings ")

    end_time = time.time()
    execution_time_seconds = end_time - start_time
    
    print(f"** Total execution time in seconds: {execution_time_seconds}")
    
    # creating metadata folder 
    metadata = {} 
    
    metadata["execution-time"] = execution_time_seconds
    metadata["llm"] = 'local'
    metadata["embedding-model"] = args.model 
    metadata["index_id"] = PRODUCT_INDEX

    metadata["vector-db"] = args.vector_type
    metadata["total-embedded-files"] = len(documents)

    json_metadata = json.dumps(metadata)

    # Write the JSON data to a file
    file_path = f"{PERSIST_FOLDER}/metadata.json"
    with open(file_path, 'w') as file:
        file.write(json_metadata)
    
    # Convert JSON data to markdown 
    markdown_content = "```markdown\n"
    for key, value in metadata.items():
        markdown_content += f"- {key}: {value}\n"
    markdown_content += "```" 
    
    file_path = f"{PERSIST_FOLDER}/metadata.md"
    with open(file_path, 'w') as file:
        file.write(markdown_content)


    return "Completed"
    
asyncio.run(main())
