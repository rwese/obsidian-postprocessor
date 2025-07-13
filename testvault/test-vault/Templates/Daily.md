<%* await tp.file.move("/Notes/Daily/" + tp.date.now("YYYY-MM-DD")) -%>
---
created: ["<% tp.date.now("YYYY-MM-DD HH:mm") %>"]
tags:
 - log/dailylog
 - todo
 - <%tp.date.now("YYYY")%>
---
# 📅 Daily <% tp.file.title %>
## New Today
- [ ]  (Due: <% tp.date.now("YYYY-MM-DD") %>)
## Daily Check List
## Tasks
```dataview
task from #todo where (due <= date(now) or !due) and !completed
```
