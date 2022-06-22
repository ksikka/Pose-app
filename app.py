# app.py
import os
import sys
import shlex
from string import Template
import lightning as L
import streamlit as st
from lai_components.run_fo_ui import FoRunUI
from lai_components.run_ui import ScriptRunUI
from lai_components.chdir_script import ChdirPythonScript
from lai_components.run_tb import RunTensorboard
from lai_components.select_fo_dataset import RunFiftyone, SelectDatasetUI
from lai_components.run_config_ui import ConfigUI

import logging
import time

# hydra.run.dir
#   outputs/YY-MM-DD/HH-MM-SS
# eval.hydra_paths
# eval_hydra_paths
#   YY-MM-DD/HH-MM-SS
predict_args="""
eval.hydra_paths=["${eval_hydra_paths}"] \
eval.test_videos_directory=${root_dir}/${eval_test_videos_directory} \
eval.saved_vid_preds_dir="${root_dir}/${hydra.run.dir}/
"""

def args_to_dict(script_args:str) -> dict:
  """convert str to dict A=1 B=2 to {'A':1, 'B':2}"""
  script_args_dict = {}
  for x in shlex.split(script_args, posix=False):
    k,v = x.split("=",1)
    script_args_dict[k] = v
  return(script_args_dict) 

# data.data_dir=./lightning-pose/toy_datasets/toymouseRunningData 
# Saved predictions to: pred_csv_files_to_plot=/home/jovyan/lightning-pose-app/lightning-pose/outputs/2022-05-15/16-06-45/predictions.csv
#             pred_csv_files_to_plot=["./lightning-pose/outputs/2022-05-15/16-06-45/predictions.csv"]  
#            test_videos_directory="./lightning-pose/toy_datasets/toymouseRunningData/unlabeled_videos" \##
#            saved_vid_preds_dir="./lightning-pose/toy_datasets/toymouseRunningData" \
#            video_file_to_plot="./lightning-pose/toy_datasets/toymouseRunningData/unlabeled_videos/test_vid.mp4" \

class LitPoseApp(L.LightningFlow):
    def __init__(self):
        super().__init__()
        # self.dataset_ui = SelectDatasetUI()
        self.args_append = None

        self.config_ui = ConfigUI(
          script_dir = "./lightning-pose",
          script_env = "HYDRA_FULL_ERROR=1",
          config_dir = "./scripts",
          config_ext = "*.yaml",        
          eval_test_videos_directory = "./lightning-pose/toy_datasets/toymouseRunningData/unlabeled_videos",     
        )

        self.train_ui = ScriptRunUI(
          script_dir = "./lightning-pose",
          script_name = "scripts/train_hydra.py",
          script_env = "HYDRA_FULL_ERROR=1",
          config_dir = "./scripts",
          config_ext = "*.yaml",        
          script_args = """training.max_epochs=11
model.losses_to_use=[]
""",
          eval_test_videos_directory = "./lightning-pose/toy_datasets/toymouseRunningData/unlabeled_videos",     
        )

        self.fo_ui = FoRunUI(
          script_dir = "./lightning-pose",
          script_name = "scripts/create_fiftyone_dataset.py",
          script_env = "HYDRA_FULL_ERROR=1",
          config_dir = "./scripts",
          script_args = """eval.fiftyone.dataset_name=test1 
eval.fiftyone.model_display_names=["test1"]
eval.fiftyone.dataset_to_create="images"
eval.fiftyone.build_speed="fast" 
eval.fiftyone.launch_app_from_script=True 
eval.video_file_to_plot=./lightning-pose/toy_datasets/toymouseRunningData/unlabeled_videos/test_vid.mp4
"""  
        )   

        # tensorboard
        self.run_tb = RunTensorboard(parallel=True, log_dir = "./lightning-pose/outputs")
        self.run_fo = RunFiftyone(parallel=True)

        # script_path is required at init, but will be override in the run
        self.train_runner = ChdirPythonScript("./lightning-pose/scripts/train_hydra.py")
        # 
        self.fo_predict_runner = ChdirPythonScript("./lightning-pose/scripts/predict_new_vids.py")
        self.fo_image_runner = ChdirPythonScript("./lightning-pose/scripts/create_fiftyone_dataset.py")
        self.fo_video_runner = ChdirPythonScript("./lightning-pose/scripts/create_fiftyone_dataset.py")


    def run(self):
      # these run in parallel
      self.run_tb.run()
      self.run_fo.run()
      # train and predict video
      if self.train_ui.run_script == True:      
        self.train_runner.run(root_dir = self.train_ui.st_script_dir, 
          script_name = self.train_ui.st_script_name, 
          script_args=self.train_ui.st_script_args,
          script_env=self.train_ui.st_script_env,
          )  
        if self.train_runner.has_succeeded:
          train_args = args_to_dict(self.train_ui.st_script_args)
          
          hydra_run_dir = train_args['hydra.run.dir']
          eval_hydra_paths = "/".join(hydra_run_dir.split("/")[-2:])
          
          eval_test_videos_directory = os.path.abspath(self.train_ui.st_eval_test_videos_directory)
          
          root_dir = os.path.abspath(self.train_ui.st_script_dir)
          
          script_args = f"eval.hydra_paths=[{eval_hydra_paths}] eval.test_videos_directory={eval_test_videos_directory} eval.saved_vid_preds_dir={hydra_run_dir}"
          
          self.fo_predict_runner.run(root_dir = self.train_ui.st_script_dir, 
            script_name = "scripts/predict_new_vids.py", 
            script_args=script_args,
            script_env=self.train_ui.st_script_env,
          )
        if self.fo_predict_runner.has_succeeded:  
          self.train_ui.run_script = False    

      # create fo dataset
      if self.fo_ui.run_script == True:      
        self.args_append = f"eval.fiftyone.dataset_name={self.fo_ui.st_dataset_name}"
        self.args_append += " " + "eval.fiftyone.model_display_names=[%s]" % ','.join([f"'{x}'" for x in self.fo_ui.st_model_display_names]) 
        self.args_append += " " + f"eval.fiftyone.launch_app_from_script=False"
        self.args_append += " " + self.fo_ui.st_hydra_config_name
        self.args_append += " " + self.fo_ui.st_hydra_config_dir

        self.fo_image_runner.run(root_dir = self.fo_ui.st_script_dir, 
          script_name = "scripts/create_fiftyone_dataset.py", 
          script_args=f"{self.fo_ui.st_script_args} eval.fiftyone.dataset_to_create=images {self.args_append}",
          script_env=self.fo_ui.st_script_env,
          )
        if self.fo_image_runner.has_succeeded:
          self.fo_video_runner.run(root_dir = self.fo_ui.st_script_dir, 
            script_name = "scripts/create_fiftyone_dataset.py", 
            script_args=f"{self.fo_ui.st_script_args} eval.fiftyone.dataset_to_create=videos {self.args_append}",
            script_env=self.fo_ui.st_script_env,
            )
        if self.fo_video_runner.has_succeeded and self.fo_image_runner.has_succeeded:   
          self.fo_ui.run_script = False

    def configure_layout(self):
        config_tab = {"name": "Lightning Pose", "content": self.config_ui}
        train_tab = {"name": "Train", "content": self.train_ui}
        train_diag_tab = {"name": "Train Diag", "content": self.run_tb}
        image_diag_prep_tab = {"name": "Image/Video Diag Prep", "content": self.fo_ui}
        image_diag_tab = {"name": "Image/Video Diag", "content": self.run_fo}
        data_anntate_tab = {"name": "Image/Video Annotation", "content": "https://cvat.org/"}
        return [config_tab, train_tab, train_diag_tab, image_diag_prep_tab, image_diag_tab, data_anntate_tab]

logging.basicConfig(level=logging.INFO)
app = L.LightningApp(LitPoseApp())
