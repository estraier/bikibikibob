#! /usr/bin/python3
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Manage files on the server
#
# Copyright 2024 Mikio Hirabayashi
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file
# except in compliance with the License.  You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the
# License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied.  See the License for the specific language governing permissions
# and limitations under the License.
#--------------------------------------------------------------------------------------------------


import cgi
import datetime
import dateutil.tz
import fcntl
import hashlib
import html
import math
import os
import re
import stat
import subprocess
import sys
import time
import unicodedata
import urllib
import urllib.parse


DATA_DIRS = [
  # label, local path, URL path, bbb.conf path
  ("input", "/home/mikio/myblog/input", "", "/home/mikio/myblog/input/bbb.conf"),
  ("data", "/home/mikio/myblog/data", "/bikibikibob/myblog/data", ""),
]
UPDATE_BBB_GENERATE = "bbb_generate.py"
NUM_FILES_IN_PAGE = 100
MAX_FILE_SIZE = 1024 * 1024 * 256
MAX_TOTAL_FILE_SIZE = 1024 * 1024 * 1024 * 16
MAX_NUM_FILES = 8192
MAX_TEXT_LENGTH = 1024 * 1024 * 4
MAX_FILENAME_LENGTH = 256
IGNORE_FILENAME_REGEXES = [
  r"^\.", r"\.(cgi)$", r"^(bbb)\.",
]
TEXT_EXTS = [
  "txt", "art", "cmt", "tsv", "csv", "json",
  "html", "xhtml", "htm", "xml",
  "css", "js",
  "c", "cc", "cxx", "h", "hxx", "java", "py", "rb", "go", "pl", "pm", "lua",
]
IMAGE_EXTS = [
  "jpg", "jpeg", "png", "gif", "tiff", "tif", "svg",
  "pnm", "pbm", "pgm", "ppm", "bmp", "heic", "heif", "webp",
]
VIDEO_EXTS = [
  "mpg", "mpeg", "mp4", "mov", "qt", "wmv", "avi", "webm",
]
CHECK_REFERRER = True
CHECK_METHOD = True
MAIN_HEADER_TEXT = r"""
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>BikiBikiBob File</title>
<style type="text/css">/*<![CDATA[*/
html {
  margin: 0;
  padding: 0;
  background: #fff;
  text-align: center;
  font-size: 12pt;
  color: #111;
  text-justify: none;
  direction: ltr;
}
body {
  display: inline-block;
  width: 100%;
  text-align: left;
  line-height: 1.0;
}
h1 {
  font-size: 120%;
}
h1 a {
  color: #000;
}
a {
  color: #02a;
  text-decoration: none;
}
a:hover {
  color: #03c;
  text-decoration: underline;
}
p.info {
  color: #01d;
}
p.error {
  color: #d00;
}
div.control_area {
  margin: 0.9ex 0;
}
table.control_table {
  margin: 0;
  border-collapse: collapse;
}
table.control_table td {
  padding: 0;
  vertical-align: top;
  white-space: nowrap;
  overflow: hidden;
  border: solid 1px #888;
}
table.control_table td.label {
  padding: 0.8ex 0.8ex;
  text-align: right;
  background: #f8f8f8;
}
table.control_table div.control_row {
  padding: 0.5ex 1.0ex;
}
table.control_table div.hidden_row {
  display: none;
  padding: 0.5ex 1.0ex;
}
div.pages_area {
  margin: 0.9ex 0;
}
div.pages_area a, div.pages_area span {
  display: inline-block;
  width: 3ex;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  font-size: 90%;
  background: #f8f8f8;
  border: solid 1px #ddd;
  border-radious: 0.5ex;
}
div.pages_area span {
  color: #888;
}
table.file_table {
  margin: 0;
  border-collapse: collapse;
}
table.file_table td, table.file_table th {
  padding: 0.5ex 1.0ex;
  vertical-align: top;
  white-space: nowrap;
  overflow: hidden;
  border: solid 1px #888;
}
table.file_table th {
  font-weight: normal;
  background: #f8f8f8;
}
table.file_table td.num {
   text-align: right;
   font-size: 90%;
   color: #333;
}
table.file_table td.name {
  position: relative;
  padding-top: 1ex;
  width: 24ex;
  font-size: 95%;
  white-space: normal;
  word-break: break-all;
}
table.file_table div.process_buttons_row {
  position: absolute;
  bottom: 1.2ex;
  right: 0.8ex;
  width: 100%;
  text-align: right;
}
table.file_table a.process_button {
  display: inline-block;
  width: 4ex;
  text-align: center;
  font-size: 90%;
  color: #111;
  text-decoration: none;
  cursor: pointer;
  border: 1pt solid #aaa;
  border-radius: 1ex;
  background: #eee;
  opacity: 0.3;
}
table.file_table a.process_button:hover {
  opacity: 1.0;
}
table.file_table td.attrs {
  padding-top: 1ex;
  font-size: 90%;
  color: #333;
}
table.file_table td.preview {
  width: 52ex;
}
table.file_table td.preview pre.preview_data {
  margin: 0;
  padding: 0;
  width: 58ex;
  max-height: 30ex;
  overflow: hidden;
  font-size: 70%;
  color: #444;
  background: #eee;
}
table.file_table td.preview img.preview_data {
  max-width: 100%;
  max-height: 30ex;
  overflow: hidden;
}
table.file_table td.preview video.preview_data {
  max-width: 100%;
  max-height: 30ex;
  overflow: hidden;
}
table.file_table td.prview span {
  color: #888;
}
div.preview_edit_area {
  margin: 1ex 1ex;
}
div.preview_edit_area div.control_row {
  padding: 1.0ex 0;
}
div.preview_edit_area span.control_cell {
  display: inline-block;
  margin-left: 2ex;
}
div.preview_edit_area textarea.edit_data {
  width: 97%;
  height: 600px;
  font-size: 85%;
  word-break: break-all;
}
div.preview_confirm_area {
  margin: 1ex 1ex;
}
div.preview_confirm_area div.preview_confirm_action {
  margin: 1ex 1ex;
}
div.preview_confirm_area input.confirm_button {
  margin: 0 1ex;
}
div.preview_confirm_area div.control_row {
  padding: 1.0ex 0;
}
div.preview_confirm_area div.hidden_row {
  display: none;
}
div.preview_confirm_area pre.preview_data {
  padding: 0.5ex 0.8ex;
  width: 95%;
  max-height: 400px;
  word-break: break-all;
  overflow: scroll;
  font-size: 70%;
  color: #444;
  background: #eee;
}
div.preview_confirm_area img.preview_data {
  max-width: 100%;
  max-height: 400px;
  overflow: hidden;
}
div.preview_confirm_area video.preview_data {
  max-width: 100%;
  max-height: 400px;
  overflow: hidden;
}
div#bbb_update_logs {
  display: none;
}
div#bbb_update_logs pre {
  width: 97%;
  margin: 0;
  padding: 0.2ex 0.5ex;
  max-height: 8em;
  font-size: 80%;
  color: #888;
  white-space: pre-wrap;
  word-break: break-all;
  background: #f8f8f8;
  border: 1pt solid #ccc;
  border-radius: 1ex;
  overflow: scroll;
}
span#proc_message {
  display: none;
  margin-left: 1.5ex;
  padding: 0.2ex 1ex;
  font-size: 85%;
  font-family: monospace;
  color: #555;
  background: #ffe;
  border: 1pt solid #eed;
  border-radius: 1ex;
}
@media screen and (min-width:750px) {
  html {
    background: #eee;
  }
  body {
    display: inline-block;
    width: 700px;
    margin: 1ex 1ex;
    padding: 1ex 2ex;
    border: 1pt solid #ccc;
    border-radius: 1ex;
    text-align: left;
    background: #fff;
  }
}
/*]]>*/</style>
<script type="text/javascript">/*<![CDATA[*/
function main() {
  adjust_control();
}
function adjust_control() {
  const input_file = document.getElementById("input_file");
  const select_name = document.getElementById("select_name");
  const filename_row = document.getElementById("filename_row");
  if (select_name.value == "assign" || select_name.value == "empty") {
    filename_row.style.display = "block";
  } else {
    filename_row.style.display = "none";
  }
  if (select_name.value == "empty") {
    input_file.disabled = "disabled";
  } else {
    input_file.disabled = null;
  }
}
function check_upload() {
  const input_file = document.getElementById("input_file");
  const select_name = document.getElementById("select_name");
  const input_filename = document.getElementById("input_filename");
  if (select_name.value != "empty" && input_file.value == "") {
    alert("No file is specified.");
    return false;
  }
  if ((select_name.value == "assign" || select_name.value == "empty") &&
      input_filename.value.trim() == "") {
    alert("The filename is empty.");
    return false;
  }
  return true;
}

function show_proc_message(message) {
  const message_elem = document.getElementById("proc_message");
  message_elem.textContent = message;
  if (message) {
    message_elem.style.display = "inline";
  } else {
    message_elem.style.display = "none";
  }
  if (message_elem.last_cleaner) {
    clearTimeout(message_elem.last_cleaner);
  }
  message_elem.last_cleaner = setTimeout(function() {
    message_elem.style.display = "none";
  }, 3000);
}

function edit_save() {
  const form = document.getElementById("edit_form");
  const bbb_update_logs = document.getElementById("bbb_update_logs");
  const dir = form.dataset.dir;
  const res = form.dataset.res;
  const digest = form.dataset.digest;
  const text = form.text.value;
  const update_bbb = form.update_bbb.value;
  show_proc_message("saving the text ...");
  bbb_update_logs.style.display = "none";
  const script_url = document.location.toString().replace(/\?.*/, "");
  const params = [];
  params.push("action=edit");
  params.push("dir=" + encodeURI(dir));
  params.push("res=" + encodeURI(res));
  params.push("digest=" + encodeURI(digest));
  params.push("text=" + encodeURI(text));
  const joined_params = params.join("&");
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      show_proc_message("saved successfully");
      for (const line of xhr.responseText.split("\n")) {
        match = line.match(/^digest=(.*)$/)
        if (match) {
          form.dataset.digest = match[1];
        }
      }
      if (update_bbb == "single") {
        bbb_generate(dir, res);
      } else if (update_bbb == "full") {
        bbb_generate(dir, "");
      }
    } else if (xhr.status == 409) {
      show_proc_message("editing conflicted; please merge the edits");
    } else {
      show_proc_message("editing failed");
    }
  }
  xhr.onerror = function() {
    alert('networking error while editing the file');
  }
  xhr.open("POST", script_url, true);
  xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
  xhr.send(joined_params);
}
function bbb_generate(dir, res) {
  const bbb_update_logs = document.getElementById("bbb_update_logs");
  show_proc_message("updating the BBB site ...");
  const script_url = document.location.toString().replace(/\?.*/, "");
  const params = [];
  params.push("action=bbb-generate");
  params.push("dir=" + encodeURI(dir));
  params.push("res=" + encodeURI(res));
  const joined_params = params.join("&");
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      show_proc_message("updated successfully");
      bbb_update_logs.style.display = "block";
      const pre = document.createElement("pre");
      pre.textContent = xhr.responseText;
      bbb_update_logs.insertBefore(pre, null);
    } else {
      show_proc_message("updating failed");
    }
  }
  xhr.onerror = function() {
    alert('networking error while updating the BBB site');
  }
  xhr.open("POST", script_url, true);
  xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
  xhr.send(joined_params);
}
function go_back() {
  const back_url = document.location.toString().replace(/action=[-a-z]+/, "action=view");
  document.location = back_url;
}
/*]]>*/</script>
</head>
<body onload="main();">
"""
MAIN_FOOTER_TEXT = r"""
</body>
</html>
"""


def main():
  request_method = os.environ.get("REQUEST_METHOD", "GET")
  script_filename = os.environ.get("SCRIPT_FILENAME", "")
  script_url = os.environ.get("REQUEST_SCHEME", "http") + "://"
  script_url += os.environ.get("HTTP_HOST", "localhost")
  script_url += os.environ.get("REQUEST_URI", "/bbb_comment.cgi")
  script_url = re.sub(r"\?.*", "", script_url)
  referrer_url = os.environ.get("HTTP_REFERER", "")
  base_dir = os.path.dirname(script_filename)
  data_dirs = []
  for label, path, url, conf in DATA_DIRS:
    path = os.path.join(base_dir, path)
    data_dirs.append((label, path, url, conf))
  if CHECK_REFERRER and referrer_url:
    script_parts = urllib.parse.urlparse(script_url)
    referrer_parts = urllib.parse.urlparse(referrer_url)
    if referrer_parts.netloc != script_parts.netloc:
      PrintError(403, "Forbidden", "bad referrer")
      return
  form = cgi.FieldStorage()
  params = {}
  for key in form.keys():
    value = form[key]
    if hasattr(value, "filename") and value.filename:
      params[key] = value.value
      params[key + "_filename"] = value.filename
    if isinstance(value, list):
      params[key] = value[0].value
    else:
      params[key] = value.value
  p_action = params.get("action", "").strip()
  p_update_bbb = params.get("update_bbb", "").strip()
  if p_action == "download":
    ProcessDownload(params, data_dirs)
    return
  if p_action == "edit":
    if CHECK_METHOD and request_method != "POST":
      SendError(403, "Forbidden", "bad method")
    else:
      ProcessEdit(params, data_dirs)
    return
  if p_action == "bbb-generate":
    if CHECK_METHOD and request_method != "POST":
      SendError(403, "Forbidden", "bad method")
    else:
      ProcessBBBGenerate(params, data_dirs)
    return
  print("Content-Type: application/xhtml+xml")
  print("")
  print(MAIN_HEADER_TEXT.strip())
  P('<h1><a href="{}">BikiBikiBob Manager</a></h1>', script_url)
  if p_action == "upload":
    if CHECK_METHOD and request_method != "POST":
      PrintError("bad method")
    else:
      ProcessUpload(params, data_dirs)
  if p_action == "remove":
    if CHECK_METHOD and request_method != "POST":
      PrintError("bad method")
    else:
      ProcessRemoval(params, data_dirs)
  PrintControl(params, data_dirs, script_url)
  if p_action == "edit-preview":
    PrintEditPreview(params, data_dirs, script_url)
  elif p_action == "remove-preview":
    PrintRemovePreview(params, data_dirs, script_url)
  else:
    PrintDirectory(params, data_dirs)
  print(MAIN_FOOTER_TEXT.strip())


def TextToInt(text):
  try:
    return int(text)
  except:
    return 0


def esc(expr):
  if expr is None:
    return ""
  return html.escape(str(expr), True)


def P(*args, end="\n"):
  esc_args = []
  for arg in args[1:]:
    if isinstance(arg, str):
      arg = esc(arg)
    esc_args.append(arg)
  print(args[0].format(*esc_args), end=end)


def PrintInfo(message):
  P('<p class="info">{}</p>', message)


def PrintError(message):
  P('<p class="error">{}</p>', message)


def NormalizeFilename(name):
  name = unicodedata.normalize("NFC", name)
  name = re.sub(r".*\\", "", name)
  name = re.sub(r".*/", "", name)
  name = re.sub(r"\s+", " ", name).strip()
  name = re.sub(r" ", "_", name)
  return name


def ReadFileDigest(path):
  h = hashlib.new("md5")
  with open(path, "rb") as input_file:
    while True:
      buf = input_file.read(8192)
      if len(buf) == 0: break
      h.update(buf)
  return h.hexdigest()


def SendError(code, status, message):
  print("Status: {} {}".format(code, status))
  print("Content-Type: text/plain; charset=UTF-8")
  print("")
  print(message)


def ProcessDownload(params, data_dirs):
  p_dir = TextToInt(params.get("dir", "1"))
  p_res = params.get("res", "")
  if p_dir < 1 or p_dir > len(data_dirs):
    SendError(404, "Not Found", "invalid dir parameter")
    return
  if p_res.find("/") >= 0 or len(p_res) > MAX_FILENAME_LENGTH:
    SendError(400, "Not Found", "invalid res parameter")
    return
  dir_label, dir_path, dir_url, dir_conf = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    SendError(404, "Not Found", "no such directory")
    return
  path = os.path.join(dir_path, p_res)
  if not os.path.exists(path):
    SendError(404, "Not Found", "no such file")
    return
  st = os.stat(path)
  if not stat.S_ISREG(st.st_mode):
    SendError(403, "Forbidden", "not a regular file")
    return
  ext = re.sub(r"^\.", "", os.path.splitext(p_res)[1].lower())
  ctype = "application/octet-stream"
  if ext in ["xhtml"]:
    ctype = "application/xhtml+xml"
  elif ext in ["html", "htm"]:
    ctype = "text/html"
  elif ext in ["xml"]:
    ctype = "text/html; charset=UTF-8"
  elif ext in TEXT_EXTS:
    ctype = "text/plain; charset=UTF-8"
  elif ext in ["jpg", "jpeg"]:
    ctype = "image/jpeg"
  elif ext in ["png"]:
    ctype = "image/png"
  elif ext in ["gif"]:
    ctype = "image/gif"
  elif ext in ["tiff", "tif"]:
    ctype = "image/gif"
  elif ext in ["svg"]:
    ctype = "image/svg+xml"
  elif ext in ["heic", "heif"]:
    ctype = "image/heif"
  elif ext in IMAGE_EXTS:
    ctype = "image/" + ext
  elif ext in ["mpg", "mpeg"]:
    ctype = "video/mpeg"
  elif ext in ["mp4"]:
    ctype = "video/mp4"
  elif ext in ["mov", "qt"]:
    ctype = "video/quicktime"
  elif ext in ["wmv"]:
    ctype = "video/x-ms-wmv"
  elif ext in ["avi"]:
    ctype = "video/x-msvideo"
  elif ext in VIDEO_EXTS:
    ctype = "video/" + ext
  with open(path, "rb") as input_file:
    print("Content-Type: " + ctype)
    print("")
    sys.stdout.flush()
    while True:
      buf = input_file.read(8192)
      if len(buf) == 0: break
      sys.stdout.buffer.write(buf)
    sys.stdout.flush()


def ProcessEdit(params, data_dirs):
  p_dir = TextToInt(params.get("dir", "1"))
  p_res = params.get("res", "")
  p_digest = params.get("digest", "")
  p_text = params.get("text")
  if p_dir < 1 or p_dir > len(data_dirs):
    SendError(404, "Not Found", "invalid dir parameter")
    return
  if p_res.find("/") >= 0 or len(p_res) > MAX_FILENAME_LENGTH:
    SendError(400, "Bad Parameter", "invalid res parameter")
    return
  dir_label, dir_path, dir_url, dir_conf = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    SendError(404, "Not Found", "no such directory")
    return
  path = os.path.join(dir_path, p_res)
  if not os.path.exists(path):
    SendError(404, "Not Found", "no such file")
    return
  st = os.stat(path)
  if not stat.S_ISREG(st.st_mode):
    PrintError(403, "Forbidden", "not a regular file")
    return
  if p_text == None:
    SendError(400, "Bad Parameter", "no text parameter")
    return
  p_text = p_text.replace("\r\n", "\n").replace("\r", "\n")
  if len(p_text) > MAX_TEXT_LENGTH:
    SendError(400, "Bad Parameter", "too larget text")
    return
  url = re.sub(r"/$", "", dir_url) + "/" + urllib.parse.quote(p_res)
  ext = re.sub(r"^\.", "", os.path.splitext(p_res)[1].lower())
  digest = ReadFileDigest(path)
  if p_digest != digest:
    SendError(409, "Conflict", "conflict with another edit")
    return
  if ext not in TEXT_EXTS:
    SendError(400, "Bad Parameter", "not a text file")
    return
  try:
    with open(path, "w") as out_file:
      out_file.write(p_text)
  except Exception as e:
    SendError(500, "Internal Server Error", "writing failed: " + str(e))
    return
  print("Content-Type: text/plain; charset=UTF-8")
  print("")
  print('The file "{}" has been updated successfully.'.format(p_res))
  new_digest = ReadFileDigest(path)
  print('digest={}'.format(new_digest))


def ProcessBBBGenerate(params, data_dirs):
  p_dir = TextToInt(params.get("dir", "1"))
  p_res = params.get("res", "")
  if p_dir < 1 or p_dir > len(data_dirs):
    SendError(404, "Not Found", "invalid dir parameter")
    return
  if p_res.find("/") >= 0 or len(p_res) > MAX_FILENAME_LENGTH:
    SendError(400, "Bad Parameter", "invalid res parameter")
    return
  dir_label, dir_path, dir_url, dir_conf = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    SendError(404, "Not Found", "no such directory")
    return
  if not dir_conf:
    SendError(403, "Forbidden", "no config is set")
    return
  if not os.path.isfile(dir_conf):
    SendError(403, "Not Found", "missing config file")
    return
  if p_res:
    ext = re.sub(r"^\.", "", os.path.splitext(p_res)[1])
    if ext != "art":
      SendError(403, "Forbidden", "not an article file")
      return
    path = os.path.join(dir_path, p_res)
    if not os.path.exists(path):
      SendError(404, "Not Found", "no such file")
      return
    st = os.stat(path)
    if not stat.S_ISREG(st.st_mode):
      PrintError(403, "Forbidden", "not a regular file")
      return
  old_env_path = os.environ.get("PATH")
  if old_env_path:
    new_env_path = old_env_path + ":/usr/local/bin:."
  else:
    new_env_path = "/bin:/usr/bin:/usr/local/bin:."
  os.environ["PATH"] = new_env_path
  command = "{} --conf {}".format(UPDATE_BBB_GENERATE, dir_conf)
  if p_res and p_res.find("'") < 0:
    command += " '{}'".format(p_res)
  try:
    fd = os.open(dir_conf, os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_EX)
    output = subprocess.Popen(
      command, stderr=subprocess.PIPE, shell=True).stderr.readlines()
    os.close(fd)
  except Exception as e:
    SendError(500, "Internal Server Error", "generating failed: " + str(e))
    return
  print("Content-Type: text/plain; charset=UTF-8")
  print()
  for line in output:
    line = line.decode()
    line = line.replace("\t", "  ").rstrip()
    print(line)


def ProcessUpload(params, data_dirs):
  p_dir = TextToInt(params.get("dir", "1"))
  p_file = params.get("file", b"")
  p_file_filename = NormalizeFilename(params.get("file_filename", ""))
  p_newname = NormalizeFilename(params.get("newname", ""))
  p_naming = params.get("naming", "local").strip()
  p_overwrite = params.get("overwrite", "stop").strip()
  if p_dir < 1 or p_dir > len(data_dirs):
    PrintError("upload failed: invalid dir parameter")
    return
  if p_naming != "empty" and (not p_file or not p_file_filename):
    PrintError("upload failed: file is not specified")
    return
  if len(p_file) > MAX_FILE_SIZE:
    PrintError("upload failed: too large file")
    return
  dir_label, dir_path, dir_url, dir_conf = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    PrintError("upload failed: no such directory")
    return
  total_file_size = len(p_file)
  num_files = 1
  for name in os.listdir(dir_path):
    ignore = False
    for ignore_regex in IGNORE_FILENAME_REGEXES:
      if re.search(ignore_regex, name):
        ignore = True
    if ignore: continue
    total_file_size += os.path.getsize(os.path.join(dir_path, name))
    num_files += 1
  if total_file_size > MAX_TOTAL_FILE_SIZE:
    PrintError("upload failed: exceeding the total file size limit")
    return
  if num_files > MAX_NUM_FILES:
    PrintError("upload failed: exceeding the file number limit")
    return
  if p_naming == "date":
    date = datetime.datetime.fromtimestamp(time.time(), dateutil.tz.tzlocal())
    filename = date.strftime("%Y%m%d%H%M%S")
  elif p_naming in ["assign", "empty"]:
    filename = p_newname
  else:
    filename = p_file_filename
  if len(filename) > MAX_FILENAME_LENGTH:
    PrintError("upload failed: too long filename")
    return
  stem, ext = os.path.splitext(filename)
  if not stem:
    PrintError("upload failed: invalid filename")
    return
  if not ext:
    ext = os.path.splitext(p_file_filename)[1]
    if ext:
      filename = filename + ext
  for ignore_regex in IGNORE_FILENAME_REGEXES:
    if re.search(ignore_regex, filename):
      PrintError("upload failed: forbidden filename")
      return
  path = os.path.join(dir_path, filename)
  if os.path.exists(path):
    if p_overwrite == "rename":
      i = 2
      while True:
        if i >= 1000:
          PrintError("upload failed: too many filename duplications")
          return
        stem, ext = os.path.splitext(filename)
        new_filename = "{}-{:d}.{}".format(stem, i, ext)
        new_path = os.path.join(dir_path, new_filename)
        if not os.path.exists(new_path):
          filename = new_filename
          path = new_path
          break
        i += 1
    elif p_overwrite == "stop":
      PrintError("upload failed: duplicated filename")
      return
  try:
    with open(path, "wb") as out_file:
      out_file.write(p_file)
  except Exception as e:
    PrintError("upload failed: " + str(e))
    return
  PrintInfo('The file "{}" has been uploaded successfully.'.format(filename))


def ProcessRemoval(params, data_dirs):
  p_dir = TextToInt(params.get("dir", "1"))
  p_res = params.get("res", "")
  p_order = params.get("order", "date_r").strip()
  p_page = TextToInt(params.get("page", "1"))
  if p_dir < 1 or p_dir > len(data_dirs):
    PrintError("removal failed: invalid dir parameter")
    return
  if p_res.find("/") >= 0 or len(p_res) > MAX_FILENAME_LENGTH:
    PrintError("removal failed: invalid res parameter")
    return
  dir_label, dir_path, dir_url, dir_conf = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    PrintError("removal failed: no such directory")
    return
  path = os.path.join(dir_path, p_res)
  if not os.path.exists(path):
    PrintError("preview failed: no such file")
    return
  st = os.stat(path)
  if not stat.S_ISREG(st.st_mode):
    PrintError("preview failed: not a regular file")
    return
  try:
    os.remove(path)
  except Exception as e:
    PrintError("removal failed: " + str(e))
    return
  PrintInfo('The file "{}" has been removed successfully.'.format(p_res))


def PrintControl(params, data_dirs, script_url):
  p_dir = TextToInt(params.get("dir", "1"))
  p_order = params.get("order", "date_r").strip()
  p_page = TextToInt(params.get("page", "1"))
  p_naming = params.get("nameing", "local")
  p_overwrite = params.get("overwrite", "stop")
  P('<div class="control_area">')
  P('<table class="control_table">')
  P('<tr>')
  P('<td class="label">View:</td>')
  P('<td class="input">')
  P('<form name="view_form" action="{}" method="GET" autocomplete="off">', script_url)
  P('<div class="control_row">')
  P('<select name="dir">')
  for i, (dir_label, dir_path, dir_url, dir_conf) in enumerate(data_dirs):
    P('<option value="{}"', i + 1, end="")
    if p_dir == i + 1: P(' selected="selected"', end="")
    P('>dir: {}</option>', dir_label)
  P('</select>')
  P('<select name="order">')
  for label, value in [("order: name asc", "name"), ("order: name desc", "name_r"),
                       ("order: size asc", "size"), ("order: size desc", "size_r"),
                       ("order: date asc", "date"), ("order: date desc", "date_r")]:
    P('<option value="{}"', value, end="")
    if p_order == value: P(' selected="selected"', end="")
    P('>{}</option>', label)
  P('</select>')
  P('<input type="submit" value="view"/>')
  P('</div>')
  P('</form>')
  P('</td>')
  P('</tr>')
  P('<tr>')
  P('<td class="label">Upload:</td>')
  P('<td class="input">')
  P('<form name="upload_form" action="{}" method="POST" enctype="multipart/form-data"'
    ' autocomplete="off" onsubmit="return check_upload();">', script_url)
  P('<div class="control_row">')
  P('<input type="file" id="input_file" name="file"/>')
  P('<select id="select_name" name="naming" onchange="adjust_control();">')
  for label, value in [("name: local", "local"), ("name: date", "date"),
                       ("name: assign", "assign"), ("empty file", "empty")]:
    P('<option value="{}"', value, end="")
    if p_naming == value: P(' selected="selected"', end="")
    P('>{}</option>', label)
  P('</select>')
  P('<select name="overwrite">')
  for label, value in [("overwrite: stop", "stop"), ("overwrite: rename", "rename"),
                       ("overwrite: force", "force")]:
    P('<option value="{}"', value, end="")
    if p_overwrite == value: P(' selected="selected"', end="")
    P('>{}</option>', label)
  P('</select>')
  P('<input type="submit" value="upload"/>')
  P('</div>')
  P('<div id="filename_row" class="hidden_row">')
  P('Filename: <input type="input" id="input_filename" name="newname" value=""/>')
  P('</div>')
  P('<div class="hidden_row">')
  P('<input type="hidden" name="action" value="upload"/>')
  P('<input type="hidden" name="dir" value="{}"/>', p_dir)
  P('<input type="hidden" name="order" value="{}"/>', p_order)
  P('<input type="hidden" name="page" value="{}"/>', p_page)
  P('</div>')
  P('</form>')
  P('</td>')
  P('</tr>')
  P('</table>')
  P('</div>')


def SizeExpr(num):
  if num > 1024 * 1024 * 1024:
    return "{:.3f}GB".format(num / 1024 / 1024 / 1024)
  if num > 1024 * 1024:
    return "{:.3f}MB".format(num / 1024 / 1024)
  if num > 1024:
    return "{:.3f}KB".format(num / 1024)
  return "{:d}B".format(num)


def DateExpr(num):
  date = datetime.datetime.fromtimestamp(num, dateutil.tz.tzlocal())
  return date.strftime("%Y/%m/%d %H:%M:%S")


def PrintDirectory(params, data_dirs):
  p_dir = TextToInt(params.get("dir", "1"))
  p_order = params.get("order", "date_r").strip()
  p_page = TextToInt(params.get("page", "1"))
  if p_dir < 1 or p_dir > len(data_dirs):
    PrintError("invalid dir parameter")
    return
  if p_page < 1:
    PrintError("invalid page parameter")
    return
  dir_label, dir_path, dir_url, dir_conf = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    PrintError("no such directory")
    return
  data_files = []
  total_size = 0
  for name in sorted(os.listdir(dir_path)):
    ignore = False
    for ignore_regex in IGNORE_FILENAME_REGEXES:
      if re.search(ignore_regex, name):
        ignore = True
    if ignore: continue
    path = os.path.join(dir_path, name)
    st = os.stat(path)
    if not stat.S_ISREG(st.st_mode): continue
    data_file = {
      "name": name,
      "path": path,
      "stat": st,
      "ext": re.sub(r"^\.", "", os.path.splitext(name)[1].lower())
    }
    data_files.append(data_file)
    total_size += st.st_size
  if not data_files:
    PrintError("no files to show")
    return
  if p_order == "name":
    data_files = sorted(data_files, key=lambda x: x["name"])
  elif p_order == "name_r":
    data_files = sorted(data_files, key=lambda x: x["name"], reverse=True)
  elif p_order == "size":
    data_files = sorted(data_files, key=lambda x: (x["stat"].st_size, x["name"]))
  elif p_order == "size_r":
    data_files = sorted(data_files, key=lambda x: (x["stat"].st_size, x["name"]), reverse=True)
  elif p_order == "date":
    data_files = sorted(data_files, key=lambda x: (x["stat"].st_mtime, x["name"]))
  elif p_order == "date_r":
    data_files = sorted(data_files, key=lambda x: (x["stat"].st_mtime, x["name"]), reverse=True)
  num_files = len(data_files)
  start_index = NUM_FILES_IN_PAGE * (p_page - 1)
  data_files = data_files[start_index:start_index+NUM_FILES_IN_PAGE]
  P('<p>There are {:d} files with {} in total.</p>',
    num_files, SizeExpr(total_size))
  def PrintPagenation():
    num_pages = math.ceil(num_files / NUM_FILES_IN_PAGE)
    P('<div class="pages_area">')
    for i in range(1, num_pages + 1):
      if i == p_page:
        P('<span>{}</span>', i)
      else:
        page_url = "?dir={}&order={}&page={}".format(p_dir, p_order, i)
        P('<a href="{}">{}</a>', page_url, i)
    P('</div>')
  PrintPagenation()
  P('<table class="file_table">')
  P('<tr>')
  P('<th>#</th>')
  P('<th>name</th>')
  P('<th>attributes</th>')
  P('<th>preview</th>')
  P('</tr>')
  for i, data_file in enumerate(data_files):
    num = i + 1 + start_index
    name = data_file["name"]
    path = data_file["path"]
    st = data_file["stat"]
    ext = data_file["ext"]
    if dir_url:
      url = re.sub(r"/$", "", dir_url) + "/" + urllib.parse.quote(name)
    else:
      url = "?action=download&res={}&dir={}".format(name, p_dir)
    P('<tr>')
    P('<td class="num">{}</td>', num)
    P('<td class="name">')
    P('<div><a href="{}">{}</a></div>', url, name)
    P('<div class="process_buttons_row">')
    if ext in TEXT_EXTS:
      edit_url = "?action=edit-preview&res={}&dir={}&order={}&page={}".format(
        name, p_dir, p_order, p_page)
      P('<a href="{}" class="process_button">ed</a>', edit_url)
    remove_url = "?action=remove-preview&res={}&dir={}&order={}&page={}".format(
      name, p_dir, p_order, p_page)
    P('<a href="{}" class="process_button">rm</a>', remove_url)
    P('</div>')
    P('</td>')
    P('<td class="attrs">')
    P('<div>{}</div>', SizeExpr(st.st_size))
    for date_expr in DateExpr(st.st_mtime).split(" "):
      P('<div>{}</div>', date_expr)
    P('</td>')
    P('<td class="preview">', end="")
    PrintPreview(ext, path, url, True)
    P('</td>', num)
    P('</tr>')
  P('</table>')
  PrintPagenation()


def PrintPreview(ext, path, url, digest):
  if ext in TEXT_EXTS:
    if digest:
      PrintPreviewTextDigest(path)
    else:
      PrintPreviewTextFull(path)
  elif ext in IMAGE_EXTS:
    PrintPreviewImage(url)
  elif ext in VIDEO_EXTS:
    PrintPreviewVideo(url)
  else:
    P('<span class="nopreview">-</span>')


def PrintEditPreview(params, data_dirs, script_url):
  p_res = params.get("res", "")
  p_dir = TextToInt(params.get("dir", "1"))
  p_order = params.get("order", "date_r").strip()
  p_page = TextToInt(params.get("page", "1"))
  p_update_bbb = params.get("update_bbb", "").strip()
  if not p_res:
    PrintError("preview failed: invalid res parameter")
    return
  if p_res.find("/") >= 0 or len(p_res) > MAX_FILENAME_LENGTH:
    PrintError("preview failed: invalid res parameter")
    return
  if p_dir < 1 or p_dir > len(data_dirs):
    PrintError("preview failed: invalid dir parameter")
    return
  dir_label, dir_path, dir_url, dir_conf = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    PrintError("preview failed: no such directory")
    return
  for ignore_regex in IGNORE_FILENAME_REGEXES:
    if re.search(ignore_regex, p_res):
      PrintError("preview failed: forbidden filename")
      return
  path = os.path.join(dir_path, p_res)
  if not os.path.exists(path):
    PrintError("preview failed: no such file")
    return
  st = os.stat(path)
  if not stat.S_ISREG(st.st_mode):
    PrintError("preview failed: not a regular file")
    return
  url = re.sub(r"/$", "", dir_url) + "/" + urllib.parse.quote(p_res)
  ext = re.sub(r"^\.", "", os.path.splitext(p_res)[1].lower())
  if ext not in TEXT_EXTS:
    PrintError("preview failed: not a text file")
    return
  digest = ReadFileDigest(path)
  P('<div class="preview_edit_area">')
  P('<p>Edit the text content and save.</p>')
  P('<div class="preview_confirm_action">')
  P('<form name="edit_form" autocomplete="off" onsubmit="return false;" id="edit_form"'
    ' data-dir="{}" data-res="{}" data-digest="{}">',
    p_dir, p_res, digest)
  P('<div class="control_row">')
  P('<input type="button" value="save" class="confirm_button" onclick="edit_save();"/>')
  P('<input type="button" value="cancel" class="confirm_button" onclick="go_back();"/>')
  if UPDATE_BBB_GENERATE and dir_conf and ext == "art":
    P('<span class="control_cell">Update BBB: ', end="")
    P('<select name="update_bbb">', end="")
    for label, value in [("no", "no"), ("single", "single"), ("full", "full")]:
      P('<option value="{}"', value, end="")
      if p_update_bbb == value:
        P(' selected="selected"', end="")
      P('>{}</option>', label, end="")
    P('</select>')
    P('</span>')
    P('<span id="proc_message"></span>')
  P('</div>')
  P('<div class="control_row" id="bbb_update_logs"></div>')
  P('<div class="control_row">')
  P('<textarea name="text" class="edit_data">', end="")
  with open(path) as input_file:
    for line in input_file:
      line = line.replace("\n", "")
      line = line.replace("\r", "")
      P('{}', line)
  P('</textarea>')
  P('</div>')
  P('<div class="hidden_row">')
  P('<input type="hidden" name="dir" value="{}"/>', p_dir)
  P('<input type="hidden" name="res" value="{}"/>', p_res)
  P('<input type="hidden" name="digest" value="{}"/>', digest)
  P('</div>')
  P('</form>')
  P('</div>')
  P('</div>')


def PrintRemovePreview(params, data_dirs, script_url):
  p_res = params.get("res", "")
  p_dir = TextToInt(params.get("dir", "1"))
  p_order = params.get("order", "date_r").strip()
  p_page = TextToInt(params.get("page", "1"))
  if not p_res:
    PrintError("preview failed: invalid res parameter")
    return
  if p_res.find("/") >= 0 or len(p_res) > MAX_FILENAME_LENGTH:
    PrintError("preview failed: invalid res parameter")
    return
  if p_dir < 1 or p_dir > len(data_dirs):
    PrintError("preview failed: invalid dir parameter")
    return
  dir_label, dir_path, dir_url, dir_conf = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    PrintError("preview failed: no such directory")
    return
  for ignore_regex in IGNORE_FILENAME_REGEXES:
    if re.search(ignore_regex, p_res):
      PrintError("preview failed: forbidden filename")
      return
  path = os.path.join(dir_path, p_res)
  if not os.path.exists(path):
    PrintError("preview failed: no such file")
    return
  st = os.stat(path)
  if not stat.S_ISREG(st.st_mode):
    PrintError("preview failed: not a regular file")
    return
  url = re.sub(r"/$", "", dir_url) + "/" + urllib.parse.quote(p_res)
  ext = re.sub(r"^\.", "", os.path.splitext(p_res)[1].lower())
  P('<div class="preview_confirm_area">')
  P('<p>Do you really remove this file?</p>')
  P('<div class="preview_confirm_action">')
  P('<form name="remove_form" action="{}" method="POST" autocomplete="off">', script_url)
  P('<div class="control_row">')
  P('<input type="submit" value="remove" class="confirm_button"/>')
  P('<input type="button" value="cancel" class="confirm_button" onclick="go_back();"/>')
  P('</div>')
  P('<div class="hidden_row">')
  P('<input type="hidden" name="action" value="remove"/>')
  P('<input type="hidden" name="dir" value="{}"/>', p_dir)
  P('<input type="hidden" name="res" value="{}"/>', p_res)
  P('<input type="hidden" name="order" value="{}"/>', p_order)
  P('<input type="hidden" name="page" value="{}"/>', p_page)
  P('</div>')
  P('</form>')
  P('</div>')
  P('<ul>')
  P('<li>dir: {}</li>', dir_label)
  P('<li>name: <b>{}</b></li>', p_res)
  P('<li>size: {}</li>', SizeExpr(st.st_size))
  P('<li>date: {}</li>', DateExpr(st.st_mtime))
  P('</ul>')
  P('<div class="preview_pane">')
  PrintPreview(ext, path, url, False)
  P('</div>')
  P('</div>')


def PrintPreviewTextDigest(path):
  P('<pre class="preview_data">', end="")
  with open(path) as input_file:
    num_line = 0
    for line in input_file:
      if num_line >= 10: break
      line = line.rstrip()[:64]
      if not line: continue
      num_line += 1
      P('{}', line)
  P('</pre>')


def PrintPreviewTextFull(path):
  P('<pre class="preview_data">', end="")
  with open(path) as input_file:
    for line in input_file:
      line = line.replace("\n", "")
      line = line.replace("\r", "")
      P('{}', line)
  P('</pre>')


def PrintPreviewImage(url):
  P('<img src="{}" class="preview_data"/>', url)


def PrintPreviewVideo(url):
  P('<video src="{}" controls="controls" preload="metadata" class="preview_data"/>', url)


if __name__=="__main__":
  main()


# END OF FILE
