"use strict";

function main() {
  adjust_images();
  check_comments();
  render_comment_history();
}

function adjust_images() {
  for (const area of document.getElementsByClassName("image_area")) {
    const area_width = area.getBoundingClientRect().width;
    const images = area.getElementsByClassName("emb_image");
    const max_area = area_width * area_width * 3 / 4;
    for (const image of images) {
      const image_area = image.width * image.height;
      if (image_area > max_area) {
        image.width = image.width * (max_area / image_area);
      }
    }
  }
}

function unescape_text(text) {
  text = text.replaceAll("\\n", "\n");
  text = text.replaceAll("\\\\", "\\");
  return text;
}

function check_comments() {
  const area = document.getElementById("comment_area");
  if (!area) return;
  const comment_url = area.dataset.commentUrl;
  const resource = area.dataset.resource;
  if (!comment_url || !resource) return;
  const request_url = comment_url + "?action=count-comments&resource=" + encodeURI(resource);
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      const lines = xhr.responseText.split("\n");
      if (lines.length >= 2) {
        const count = parseInt(lines[0]);
        const date = parseInt(lines[1]);
        update_comment_banner(count, date);
      }
    }
  };
  xhr.onerror = function() {
    alert('networking error while counting comments')
  };
  xhr.open("GET", request_url, true);
  xhr.send();
}

function update_comment_banner(count, date) {
  const banner = document.getElementById("comment_banner");
  const comment_count = document.createElement("span");
  comment_count.className = "comment_count";
  comment_count.textContent = "(" + count + ")";
  banner.insertBefore(comment_count, null);
  if (count > 0) {
    const diff = new Date().getTime() / 1000 - date;
    if (diff < 60 * 60 * 24 * 2) {
      banner.classList.add("comment_recent");
    } else {
      banner.classList.add("comment_filled");
    }
  }
}

function render_comments() {
  const area = document.getElementById("comment_area");
  if (!area) return;
  const comment_url = area.dataset.commentUrl;
  const resource = area.dataset.resource;
  if (!comment_url || !resource) return;
  const banner = document.getElementById("comment_banner");
  banner.style.display = "none";
  const request_url = comment_url + "?action=list-comments&resource=" + encodeURI(resource);
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      const comments = [];
      for (const line of xhr.responseText.split("\n")) {
        const fields = line.split("\t");
        if (fields.length != 3) continue;
        const comment = {}
        comment.date = fields[0];
        comment.author = fields[1];
        comment.text = unescape_text(fields[2]);
        comments.push(comment);
      }
      update_comment_list(comments)
      window.scrollTo(0, document.body.scrollHeight);
    }
  };
  xhr.onerror = function() {
    alert('networking error while getting comments')
  };
  xhr.open("GET", request_url, true);
  xhr.send();
  const author_elem = document.getElementById("comment_author");
  if (author_elem.value.length == 0) {
    const saved_user_name = load_user_name();
    if (saved_user_name) {
      author_elem.value = saved_user_name;
    }
  }
}

function update_comment_list(comments) {
  const pane = document.getElementById("comment_list");
  pane.style.display = "block";
  pane.innerHTML = "";
  for (const comment of comments) {
    const comment_item = document.createElement("div");
    comment_item.className = "comment_item";
    const comment_date = document.createElement("div");
    comment_date.className = "comment_date";
    comment_date.textContent = comment.date;
    comment_item.insertBefore(comment_date, null);
    const comment_author = document.createElement("div");
    comment_author.className = "comment_author";
    comment_author.textContent = comment.author;
    comment_item.insertBefore(comment_author, null);
    const comment_text = document.createElement("div");
    comment_text.className = "comment_text";
    comment_text.textContent = comment.text;
    comment_item.insertBefore(comment_text, null);
    pane.insertBefore(comment_item, null);
  }
  if (comments.length < 1) {
    const comment_item = document.createElement("div");
    comment_item.className = "comment_item";
    const comment_message = document.createElement("div");
    comment_message.className = "comment_message";
    comment_message.textContent = "(no comments yet)";
    comment_item.insertBefore(comment_message, null);
    pane.insertBefore(comment_item, null);
  }
  const form = document.getElementById("comment_form");
  form.style.display = "block";  
}

function post_comment() {
  const area = document.getElementById("comment_area");
  if (!area) return;
  const comment_url = area.dataset.commentUrl;
  const resource = area.dataset.resource;
  const author_elem = document.getElementById("comment_author");
  const text_elem = document.getElementById("comment_text");
  const author = author_elem.value;
  const text = text_elem.value;
  if (author.trim().length < 1) {
    show_comment_message("empty author");
    return;
  }
  if (author.length > 30) {
    show_comment_message("too long name (must be up to 30 characters)");
    return;
  }
  if (text.trim().length < 1) {
    show_comment_message("empty text");
    return;
  }
  if (text.length > 3000) {
    show_comment_message("too long text (must be up to 3000 characters)");
    return;
  }
  let current_time = new Date().getTime() / 1000;
  if (area.last_post_time && current_time - area.last_post_time < 10) {
    show_comment_message("too quick; please wait for a moment");
    return;
  }
  show_comment_message("checking the nonce ...");
  const request_url = comment_url + "?action=get-nonce&resource=" + encodeURI(resource);
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      const nonce = xhr.responseText.trim();
      post_comment_second(comment_url, resource, author, text, nonce);
    } else {
      show_comment_message("cannot get the nonce");
    }
  };
  xhr.onerror = function() {
    alert('networking error while checking the nonce')
  };
  xhr.open("GET", request_url, true);
  xhr.send();
}

function post_comment_second(comment_url, resource, author, text, nonce) {
  const area = document.getElementById("comment_area");
  const text_elem = document.getElementById("comment_text");
  show_comment_message("posting the comment ...");
  const params = [];
  params.push("action=post-comment");
  params.push("resource=" + encodeURI(resource));
  params.push("author=" + encodeURI(author));
  params.push("text=" + encodeURI(text));
  params.push("nonce=" + encodeURI(nonce));
  const joined_params = params.join("&");
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      show_comment_message("posted successfully");
      text_elem.value = "";
      let current_time = new Date().getTime() / 1000;
      area.last_post_time = current_time;
      render_comments();
      save_user_name(author);
    } else if (xhr.status == 409) {
      show_comment_message("posting conflicted; please try again");
    } else {
      show_comment_message("posting failed");
    }
  }
  xhr.onerror = function() {
    alert('networking error while posting the comment')
  }
  xhr.open("POST", comment_url, true);
  xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
  xhr.send(joined_params);
}

function show_comment_message(message) {
  const message_elem = document.getElementById("comment_message");
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

function save_user_name(name) {
  if (!localStorage) return;
  return localStorage.setItem("user_name", name);
}

function load_user_name() {
  if (!localStorage) return null;
  return localStorage.getItem("user_name");
}

function render_comment_history() {
  for (const area of document.getElementsByClassName("comment_history_area")) {
    const comment_url = area.dataset.commentUrl;
    const max = area.dataset.commentMax;
    const request_url = comment_url + "?action=list-history&max=" + max;
    const xhr = new XMLHttpRequest();
    xhr.onload = function() {
      if (xhr.status == 200) {
        const comments = [];
        for (const line of xhr.responseText.split("\n")) {
          const fields = line.split("\t");
          if (fields.length != 5) continue;
          const comment = {}
          comment.date = fields[0];
          comment.resource = fields[1];
          comment.title = fields[2];
          comment.author = fields[3];
          comment.text = fields[4];
          comments.push(comment);
        }
        update_comment_history(area, comments);
      }
    };
    xhr.onerror = function() {
      alert('networking error while getting comment history')
    };
    xhr.open("GET", request_url, true);
    xhr.send();
  }
}

function update_comment_history(area, comments) {
  area.innerHTML = "";
  if (comments.length > 0) {
    const history_list = document.createElement("ul");
    for (const comment of comments) {
      const history_item = document.createElement("li");
      history_item.className = "history_item";
      const history_author = document.createElement("span");
      history_author.className = "history_author";
      history_author.textContent = comment.author;
      history_item.insertBefore(history_author, null);
      history_item.insertBefore(
        document.createTextNode(" commented "), null);
      const history_text = document.createElement("span");
      history_text.className = "history_text";
      history_text.textContent = '"' + comment.text + '"';
      history_item.insertBefore(history_text, null);
      history_item.insertBefore(
        document.createTextNode(" on "), null);
      const history_resource = document.createElement("a");
      history_resource.className = "history_resource";
      if (comment.title == "") {
        history_resource.textContent = comment.resource;
      } else {
        history_resource.textContent = '"' + comment.title + '"';
      }
      history_resource.href = "./" + comment.resource + ".xhtml";
      history_item.insertBefore(history_resource, null);
      history_item.insertBefore(
        document.createTextNode(" at "), null);
      const history_date = document.createElement("span");
      history_date.className = "history_date";
      history_date.textContent = comment.date;
      history_item.insertBefore(history_date, null);
      history_list.insertBefore(history_item, null);
    }
    area.insertBefore(history_list, null);
  } else {
    const history_message = document.createElement("div");
    history_message.className = "history_message";
    history_message.textContent = "(no comments yet)";
    area.insertBefore(history_message, null);
  }
}

// END OF FILE
