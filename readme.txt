============================================================
  Disaster Prediction Pipeline — Setup & Usage Guide
============================================================

OVERVIEW
--------
This pipeline performs real-time disaster analysis by combining:
  - Satellite flood images (streamed via TCP)
  - Live Twitter/social media data
  - Live weather data
All of this is processed through Kafka + Spark and displayed on
a Flask real-time dashboard.


------------------------------------------------------------
STEP 1 — SET UP THE ENVIRONMENT
------------------------------------------------------------
1) Create and activate the conda environment:

   conda create -n disaster_detect python=3.10
   conda activate disaster_detect

2) Install all required dependencies:

   pip install pandas torch transformers opencv-python numpy \
               pyspark flask flask-socketio kafka-python requests


------------------------------------------------------------
STEP 2 — CREATE THE DATA DIRECTORY STRUCTURE
------------------------------------------------------------
The 'data/' folder is NOT included in this repository (excluded
because it contains large dataset files). You must create it
manually with the following structure:

   Disaster_Prediction/
   └── data/
       ├── flood_dataset/
       │   ├── images/      <-- Put your flood .jpg images here
       │   └── masks/       <-- Put corresponding .png masks here
       ├── simulated_stream/   <-- Will be auto-created at runtime
       └── twitter_data/       <-- Will be auto-created at runtime

Run these commands from the project root to create the folders:

   mkdir -p data/flood_dataset/images
   mkdir -p data/flood_dataset/masks
   mkdir -p data/simulated_stream
   mkdir -p data/twitter_data

Then place your flood dataset images inside:
   data/flood_dataset/images/   → flood image files (.jpg)
   data/flood_dataset/masks/    → segmentation mask files (.png)
   (Image and mask filenames must match, e.g. 1.jpg <-> 1.png)


------------------------------------------------------------
STEP 3 — TRAIN THE FLOOD DETECTION MODEL (U-Net)
------------------------------------------------------------
The flood segmentation model weights are NOT included in the
repository. You must train the model yourself first.

1) Make sure your flood dataset images and masks are in place
   (see Step 2 above).

2) Navigate to the flood detection training folder:

   cd ml_models/flood_detection

3) Run the training script:

   python train.py

   This will train a U-Net model for 15 epochs on your dataset
   and save the weights as:
      ml_models/flood_detection/flood_unet_cpu.pth

   NOTE: Training time depends on your dataset size and hardware.
   The model trains on CPU by default.


------------------------------------------------------------
STEP 4 — TRAIN THE TWITTER SENTIMENT MODEL (BERT)
------------------------------------------------------------
The Twitter/social media disaster classifier is also NOT included.
You must fine-tune it using the provided Jupyter notebook.

1) Navigate to the twitter folder:

   cd twitter

2) Open the training notebook:

   jupyter notebook flood_twitter_data_train.ipynb

3) Run all cells in the notebook. This will fine-tune a BERT-based
   model on flood-related tweet data and save the model files to:
      ml_models/twitter_model/
          config.json
          model.safetensors
          tokenizer.json
          tokenizer_config.json
          training_args.bin

   Make sure these files exist before running the pipeline.


------------------------------------------------------------
STEP 5 — RUN THE PIPELINE (3 Terminals Required)
------------------------------------------------------------

>> TERMINAL 1 — Start the Image Receiver (TCP Server)

   Navigate to the satellite/ directory and start the receiver.
   This opens a TCP server on port 5001 that waits for incoming
   satellite images and saves them to data/simulated_stream/:

   cd satellite
   python get_stream.py

   You will see:  "Waiting for sender..."
   Keep this terminal running.


>> TERMINAL 2 — Start the Main Analysis Pipeline

   While Terminal 1 is running and waiting, open a NEW terminal.
   Navigate to spark_jobs/ and start the full analysis pipeline:

   cd spark_jobs
   python analysis.py

   This will automatically:
     - Start ZooKeeper (port 2181)
     - Start Kafka Broker (port 9092)
     - Launch the flood image Spark streaming job
     - Launch the Twitter data streaming job
     - Launch the weather data streaming job
     - Start the Flask dashboard at http://localhost:5000

   Open your browser and go to:  http://localhost:5000
   Keep this terminal running.


>> TERMINAL 3 — Send Satellite Images (TCP Client)

   Once Terminal 1 shows "Waiting for sender..." and Terminal 2
   has the Flask server running, open a THIRD terminal and send
   the flood images through the TCP stream:

   cd satellite
   python send_stream.py

   This reads images from data/flood_dataset/images/ and streams
   them one by one (every 3 seconds) to the receiver in Terminal 1,
   which drops them into data/simulated_stream/ for Spark to pick
   up and analyze in real time.


------------------------------------------------------------
STEP 6 — VIEW REAL-TIME RESULTS
------------------------------------------------------------
Open your browser and visit:

   http://localhost:5000

The dashboard will display:
  - Live flood detection results from satellite images
  - Twitter sentiment analysis for disaster-related tweets
  - Live weather data and alerts

To stop the pipeline, press Ctrl+C in Terminal 2 (analysis.py).
ZooKeeper and Kafka will shut down gracefully.


------------------------------------------------------------
PROJECT STRUCTURE
------------------------------------------------------------
Disaster_Prediction/
├── data/                        # (Not in repo — create manually)
│   ├── flood_dataset/
│   │   ├── images/              # Flood .jpg images for training
│   │   └── masks/               # Segmentation .png masks
│   └── simulated_stream/        # Auto-created — incoming images
├── kafka/                       # Kafka binary distribution
│   ├── bin/                     # Kafka/ZooKeeper startup scripts
│   ├── config/                  # Kafka configuration files
│   └── libs/                    # Kafka JAR dependencies
├── ml_models/
│   ├── flood_detection/
│   │   ├── train.py             # U-Net training script
│   │   └── flood_unet_cpu.pth   # (Generated after training)
│   └── twitter_model/           # (Generated after notebook run)
│       ├── model.safetensors
│       ├── tokenizer.json
│       └── config.json
├── satellite/
│   ├── get_stream.py            # TCP server — receives images
│   └── send_stream.py           # TCP client — sends images
├── spark_jobs/
│   ├── analysis.py              # MAIN ENTRY POINT — run this
│   ├── streaming.py             # Spark flood image stream job
│   ├── twitter_stream.py        # Twitter Kafka producer
│   ├── weather_stream.py        # Weather Kafka producer
│   ├── frontend.py              # Flask + SocketIO server
│   └── frontend/
│       └── index.html           # Real-time dashboard UI
├── twitter/
│   ├── flood_twitter_data_train.ipynb  # BERT fine-tuning notebook
│   └── predict_score.py         # Twitter inference helper
└── readme.txt                   # This file


------------------------------------------------------------
QUICK REFERENCE — COMMAND SUMMARY
------------------------------------------------------------
# Environment
conda activate disaster_detect

# Create data directories
mkdir -p data/flood_dataset/images data/flood_dataset/masks \
         data/simulated_stream data/twitter_data

# Train flood model
cd ml_models/flood_detection && python train.py

# Train Twitter model (run all cells)
cd twitter && jupyter notebook flood_twitter_data_train.ipynb

# Terminal 1: Start image receiver
cd satellite && python get_stream.py

# Terminal 2: Start full pipeline + dashboard
cd spark_jobs && python analysis.py

# Terminal 3: Stream images into the pipeline
cd satellite && python send_stream.py

# View dashboard
Open browser → http://localhost:5000