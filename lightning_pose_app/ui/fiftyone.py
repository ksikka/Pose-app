from lightning import CloudCompute, LightningFlow
from lightning.app.utilities.state import AppState
import os
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import yaml

from lightning_pose_app.bashwork import LitBashWork
from lightning_pose_app.build_configs import LitPoseBuildConfig, lightning_pose_dir
from lightning_pose_app.utilities import args_to_dict, dict_to_args, StreamlitFrontend


class FiftyoneUI(LightningFlow):
    """UI to run Fiftyone and Streamlit apps."""

    def __init__(
        self,
        *args,
        drive_name,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.work = LitBashWork(
            cloud_compute=CloudCompute("default"),
            cloud_build_config=LitPoseBuildConfig(),  # get fiftyone
            drive_name=drive_name,
            wait_seconds_after_run=1,
            wait_seconds_after_kill=1,
        )

        # control runners
        # True = Run Jobs.  False = Do not Run jobs
        # UI sets to True to kickoff jobs
        # Job Runner sets to False when done
        self.run_script = False

        # params updated externally by top-level flow
        self.fiftyone_datasets = []
        self.trained_models = []
        self.proj_dir = None
        self.config_name = None

        # submit count
        self.submit_count = 0

        # output from the UI
        self.st_script_args = """
            eval.fiftyone.dataset_to_create="images"
            eval.fiftyone.build_speed="fast"
            eval.fiftyone.remote=true
        """
        self.st_script_args_append = None
        self.st_submit = False
        self.st_dataset_name = None
        self.submit_success = False

    def start_fiftyone(self):
        """run fiftyone"""
        cmd = "fiftyone app launch --address $host --port $port --remote"
        self.work.run(cmd, wait_for_exit=True, cwd=lightning_pose_dir)

    def find_fiftyone_datasets(self):
        """get existing fiftyone datasets"""
        # NOTE: we could migrate the fiftyone database back and forth between the Drive but this
        # seems lke overkill? the datasets are quick to make and users probably don't care so much
        # about these datasets; can return to this later
        cmd = "fiftyone datasets list"
        self.work.run(cmd, save_stdout=True)
        if self.work.last_args() == cmd:
            names = []
            print(self.work.stdout)
            for x in self.work.stdout:
                if x.endswith("No datasets found"):
                    continue
                if x.startswith("Migrating database"):
                    continue
                if x.endswith("python"):
                    continue
                if x in names:
                    continue
                names.append(x)
            self.fiftyone_datasets = names
        else:
            pass

    def build_fiftyone_dataset(self):
        cmd = "python scripts/create_fiftyone_dataset.py" \
              + " " + self.st_script_args_append \
              + " " + self.st_script_args \
              + " " + "eval.fiftyone.dataset_to_create=images" \
              + " " + "+eval.fiftyone.n_dirs_back=6"  # hack
        self.work.run(
            cmd, 
            cwd=lightning_pose_dir, 
            timer=self.st_dataset_name,
            inputs=[os.path.join(self.proj_dir, self.config_name)],
        )

        # add dataset name to list for user to see
        self.fiftyone_datasets.append(self.st_dataset_name)

    def run(self, action, **kwargs):

        if action == "find_fiftyone_datasets":
            self.find_fiftyone_datasets()
        elif action == "start_fiftyone":
            self.start_fiftyone()
        elif action == "build_fiftyone_dataset":
            self.build_fiftyone_dataset()

    def configure_layout(self):
        return StreamlitFrontend(render_fn=_render_streamlit_fn)


def set_script_args(model_dirs: [str], script_args: str):

    script_args_dict = args_to_dict(script_args)

    # enrich the args
    # eval.video_file_to_plot="</ABSOLUTE/PATH/TO/VIDEO.mp4>" \
    # eval.hydra_paths=["</ABSOLUTE/PATH/TO/HYDRA/DIR/1>","</ABSOLUTE/PATH/TO/HYDRA/DIR/1>"] \
    # eval.fiftyone.model_display_names=["<NAME_FOR_MODEL_1>","<NAME_FOR_MODEL_2>"]
    # eval.pred_csv_files_to_plot=["</ABSOLUTE/PATH/TO/PREDS_1.csv>","</ABSOLUTE/PATH/TO/PREDS_2.csv>"]

    if model_dirs:
        path_list = ','.join([f"'{x}'" for x in model_dirs])
        script_args_dict["eval.hydra_paths"] = f"[{path_list}]"

    # these will be controlled by the runners. remove if set manually
    script_args_dict.pop('eval.fiftyone.address', None)
    script_args_dict.pop('eval.fiftyone.port', None)
    script_args_dict.pop('eval.fiftyone.launch_app_from_script', None)
    script_args_dict.pop('eval.fiftyone.dataset_to_create', None)
    script_args_dict.pop('eval.fiftyone.dataset_name', None)
    script_args_dict.pop('eval.fiftyone.model_display_names', None)

    return dict_to_args(script_args_dict), script_args_dict


def _render_streamlit_fn(state: AppState):
    """Create Fiftyone Dataset"""

    # force rerun to update page
    st_autorefresh(interval=2000, key="refresh_page")

    st.markdown(
        """
        ## Prepare Fiftyone diagnostics

        Choose two models for evaluation.

        """
    )

    st.markdown(
        """
        #### Select models
        """
    )

    # hard-code two models for now
    st_model_dirs = [None for _ in range(2)]
    st_model_display_names = [None for _ in range(2)]

    # ---------------------------------------------------------
    # collect input from users
    # ---------------------------------------------------------
    with st.form(key="fiftyone_form", clear_on_submit=True):

        col0, col1 = st.columns(2)

        with col0:

            # select first model (supervised)
            options1 = sorted(state.trained_models, reverse=True)
            tmp = st.selectbox("Select Model 1", options=options1, disabled=state.run_script)
            st_model_dirs[0] = tmp
            tmp = st.text_input(
                "Display name for Model 1", value="model_1", disabled=state.run_script)
            st_model_display_names[0] = tmp

        with col1:

            # select second model (semi-supervised)
            options2 = sorted(state.trained_models, reverse=True)
            if st_model_dirs[0]:
                options2.remove(st_model_dirs[0])

            tmp = st.selectbox("Select Model 2", options=options2, disabled=state.run_script)
            st_model_dirs[1] = tmp
            tmp = st.text_input(
                "Display name for Model 2", value="model_2", disabled=state.run_script)
            st_model_display_names[1] = tmp

        # make model dirs absolute paths
        for i in range(2):
            if st_model_dirs[i] and not os.path.isabs(st_model_dirs[i]):
                st_model_dirs[i] = os.path.join(
                    os.getcwd(), state.proj_dir, "models", st_model_dirs[i])

        # dataset names
        existing_datasets = state.fiftyone_datasets
        st.write(f"Existing Fifityone datasets:\n{', '.join(existing_datasets)}")
        st_dataset_name = st.text_input(
            "Choose dataset name other than the above existing names", disabled=state.run_script)

        # parse
        st_script_args, script_args_dict = set_script_args(
            model_dirs=st_model_dirs, script_args=state.st_script_args)

        # build dataset
        st.markdown("""
            Click to begin preparation of the Fiftyone dataset. 
            These diagnostics will be displayed in the following 'Fiftyone' tab.
            """)
        st_submit_button = st.form_submit_button("Initialize fiftyone", disabled=state.run_script)

    # ---------------------------------------------------------
    # check user input
    # ---------------------------------------------------------
    if st_model_display_names[0] is None \
            or st_model_display_names[1] is None \
            or st_model_display_names[0] == st_model_display_names[1]:
        st_submit_button = False
        state.submit_success = False
        st.warning(f"Must choose two unique model display names")
    if st_model_dirs[0] is None or st_model_dirs[1] is None:
        st_submit_button = False
        state.submit_success = False
        st.warning(f"Must choose two models to continue")
    if st_submit_button and \
            (st_dataset_name in existing_datasets
             or st_dataset_name is None
             or st_dataset_name == ""):
        st_submit_button = False
        state.submit_success = False
        st.warning(f"Enter a unique dataset name to continue")
    if state.run_script:
        st.warning(f"Waiting for existing dataset creation to finish "
                   f"(may take 30 seconds to update)")
    if state.submit_count > 0 \
            and not state.run_script \
            and not st_submit_button \
            and state.submit_success:
        proceed_str = "Diagnostics are ready to view in the following tab."
        proceed_fmt = "<p style='font-family:sans-serif; color:Green;'>%s</p>"
        st.markdown(proceed_fmt % proceed_str, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # build fiftyone dataset
    # ---------------------------------------------------------
    # this will only be run once when the user clicks the button; 
    # on the following pass the button click will be set to False again
    if st_submit_button:

        state.submit_count += 1

        # save streamlit options to flow object only on button click
        state.st_dataset_name = st_dataset_name
        state.st_script_args = st_script_args

        # set key-value pairs that will be used as script args
        model_names = ','.join([f"'{x}'" for x in st_model_display_names])
        script_args_append = f" --config-path={os.path.join(os.getcwd(), state.proj_dir)}"
        script_args_append += f" --config-name={state.config_name}"
        script_args_append += f" eval.fiftyone.dataset_name={st_dataset_name}"
        script_args_append += f" eval.fiftyone.model_display_names=[{model_names}]"
        script_args_append += f" eval.fiftyone.launch_app_from_script=false"
        state.st_script_args_append = script_args_append

        # reset form
        st_dataset_name = None
        st_model_dirs = [None for _ in range(2)]
        st_model_display_names = [None for _ in range(2)]

        st.text("Request submitted!")
        state.submit_success = True
        state.run_script = True  # must the last to prevent race condition

        # force rerun to update warnings
        st_autorefresh(interval=2000, key="refresh_diagnostics_submitted")
