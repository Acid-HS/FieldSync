use crate::args;
use std::process::{self, Command};
use std::env;

pub fn run_cmd(mut cmd: Command) {
    rap_trace!("Command is: {:?}.", cmd);
    match cmd.status() {
        Ok(status) => {
            if !status.success() {
                process::exit(status.code().unwrap());
            }
        }
        Err(err) => panic!("Error in running {:?} {}.", cmd, err),
    }
}

pub fn run_rustc() {
    let mut cmd = Command::new("rustc");
    cmd.args(args::skip2());
    run_cmd(cmd);
}

pub fn run_rap() {
    let current_exe = env::current_exe().expect("failed to get current executable path");
    let rapx_path = current_exe.with_file_name(format!("rapx{}", env::consts::EXE_SUFFIX));

    rap_trace!("Resolved local rapx path: {:?}", rapx_path);

    let mut cmd = Command::new(&rapx_path);
    cmd.args(args::skip2());
    run_cmd(cmd);
}
