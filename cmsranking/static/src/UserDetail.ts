/* Programming contest management system
 * Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 */

import * as $ from "jquery";

import { Chart } from "./Chart";
import { Config } from "./Config";
import { DataStore, round_to_str } from "./DataStore";
import { HistoryStore } from "./HistoryStore";
import { format_time } from "./TimeView";

class UserDetail {
    private static instance: UserDetail;

    private historyStore: HistoryStore;

    private f_name_label: JQuery<HTMLElement>;
    private l_name_label: JQuery<HTMLElement>;
    private team_label: JQuery<HTMLElement>;
    private flag_image: JQuery<HTMLElement>;
    private face_image: JQuery<HTMLElement>;
    private title_label: JQuery<HTMLElement>;
    private navigator: JQuery<HTMLElement>;
    private submission_table: JQuery<HTMLElement>;
    private score_chart: HTMLCanvasElement;
    private rank_chart: HTMLCanvasElement;

    private active;
    private user_id: string;
    private user;
    private data_fetched: number;
    private task_s;
    private task_r;
    private contest_s;
    private contest_r;
    private submissions;
    private global_s: any[];
    private global_r: any[];

    public static getInstance() {
      if (!UserDetail.instance) {
        UserDetail.instance = new UserDetail();
      }
      return UserDetail.instance;
    }

    private constructor() {
        this.historyStore = HistoryStore.getInstance();
        $("#UserDetail_bg").click((event) => {
            if (event.target == event.currentTarget) {
                this.hide();
            }
        });

        $("#UserDetail_close").click(() => {
            this.hide();
        });

        $(document).keyup((event) => {
            if (event.keyCode == 27) { // ESC key
                this.hide();
            }
        });

        this.f_name_label = $('#UserDetail_f_name');
        this.l_name_label = $('#UserDetail_l_name');
        this.team_label = $('#UserDetail_team');
        this.flag_image = $('#UserDetail_flag');
        this.face_image = $('#UserDetail_face');
        this.title_label = $('#UserDetail_title');

        this.navigator = $('#UserDetail_navigator table tbody');
        this.submission_table = $('#UserDetail_submissions');

        this.score_chart =
          $('#UserDetail_score_chart')[0] as HTMLCanvasElement;
        this.rank_chart =
          $('#UserDetail_rank_chart')[0] as HTMLCanvasElement;

        this.navigator.on("click", "td.btn", () => {
            if (this.active !== null) {
                this.active.removeClass("active");
            }
            this.active = $(this).parent();
            this.active.addClass("active");

            if (this.active.hasClass('global')) {
                this.show_global();
            } else if (this.active.hasClass('contest')) {
                this.show_contest(this.active.attr('data-contest'));
            } else if (this.active.hasClass('task')) {
                this.show_task(this.active.attr('data-task'));
            }
        });

        window.addEventListener("hashchange", this.toggle_visibility_from_hash.bind(this));
        this.toggle_visibility_from_hash();
    };

    private get_current_hash() {
        return window.location.hash.substr(1);
    }

    private toggle_visibility_from_hash() {
        var user_id = this.get_current_hash();
        if (user_id == "") {
            // No user requested, hide the details if they were open.
            this.hide();
        } else if (!DataStore.users.hasOwnProperty(user_id)) {
            // Non-existing user, do as if the request was without the hash.
            window.history.replaceState(
                {}, "", window.location.href.replace(/#.*$/, ''));
            this.hide();
        } else {
            // Some valid user requested, show the details.
            this.show(user_id);
        }
    }

    private show(user_id) {
        this.user_id = user_id;
        this.user = DataStore.users[user_id];
        this.data_fetched = 0;

        if (this.get_current_hash() != user_id) {
            window.history.pushState({}, "", "#" + user_id);
        }
        window.document.title =
            "Ranking - " + this.user["f_name"] + " " + this.user["l_name"];

        this.historyStore.request_update(this.history_callback.bind(this));

        $.ajax({
            url: Config.get_submissions_url(this.user_id),
            dataType: "json",
            success: this.submissions_callback.bind(this),
            error: function () {
                console.error("Error while getting the submissions for " + this.user_id);
            }
        });
    }

    private history_callback() {
        this.task_s = new Object();
        this.task_r = new Object();
        for (var t_id in DataStore.tasks) {
            this.task_s[t_id] = this.historyStore.get_score_history_for_task(this.user_id, t_id);
            this.task_r[t_id] = this.historyStore.get_rank_history_for_task(this.user_id, t_id);
        }

        this.contest_s = new Object();
        this.contest_r = new Object();
        for (var c_id in DataStore.contests) {
            this.contest_s[c_id] = this.historyStore.get_score_history_for_contest(this.user_id, c_id);
            this.contest_r[c_id] = this.historyStore.get_rank_history_for_contest(this.user_id, c_id);
        }

        this.global_s = this.historyStore.get_score_history(this.user_id);
        this.global_r = this.historyStore.get_rank_history(this.user_id);

        this.data_fetched += 1;
        this.do_show();
    }

    private submissions_callback(data) {
        this.submissions = new Object();
        for (var t_id in DataStore.tasks) {
            this.submissions[t_id] = new Array();
        }
        for (var i = 0; i < data.length; i += 1) {
            var submission = data[i];
            this.submissions[submission['task']].push(submission);
        }

        this.data_fetched += 1;
        this.do_show();
    }

    private do_show() {
        if (this.data_fetched == 2) {
            this.f_name_label.text(this.user["f_name"]);
            this.l_name_label.text(this.user["l_name"]);
            this.face_image.attr("src", Config.get_face_url(this.user_id));

            if (this.user["team"]) {
                this.team_label.text(DataStore.teams[this.user["team"]]["name"]);
                this.flag_image.attr("src", Config.get_flag_url(this.user['team']));
                this.flag_image.removeClass("hidden");
            } else {
                this.team_label.text("");
                this.flag_image.addClass("hidden");
            }

            var s = "<tr class=\"global\"> \
                        <td class=\"name\">Global</td> \
                        <td class=\"score\">" + (this.global_s.length > 0 ? round_to_str(this.global_s[this.global_s.length-1][1], DataStore.global_score_precision) : 0) + "</td> \
                        <td class=\"rank\">" + (this.global_r.length > 0 ? this.global_r[this.global_r.length-1][1] : 1) + "</td> \
                        <td class=\"btn\"><a>Show</a></td> \
                    </tr>";

            var contests = DataStore.contest_list;
            for (var i in contests) {
                var contest = contests[i];
                var c_id = contest["key"];

                s += "<tr class=\"contest\" data-contest=\"" + c_id +"\"> \
                         <td class=\"name\">" + contest['name'] + "</td> \
                         <td class=\"score\">" + (this.contest_s[c_id].length > 0 ? round_to_str(this.contest_s[c_id][this.contest_s[c_id].length-1][1], contest["score_precision"]) : 0) + "</td> \
                         <td class=\"rank\">" + (this.contest_r[c_id].length > 0 ? this.contest_r[c_id][this.contest_r[c_id].length-1][1] : 1) + "</td> \
                         <td class=\"btn\"><a>Show</a></td> \
                      </tr>"

                var tasks = contest["tasks"];
                for (var j in tasks) {
                    var task = tasks[j];
                    var t_id = task["key"];

                    s += "<tr class=\"task\" data-task=\"" + t_id +"\"> \
                             <td class=\"name\">" + task['name'] + "</td> \
                             <td class=\"score\">" + (this.task_s[t_id].length > 0 ? round_to_str(this.task_s[t_id][this.task_s[t_id].length-1][1], task["score_precision"]) : 0) + "</td> \
                             <td class=\"rank\">" + (this.task_r[t_id].length > 0 ? this.task_r[t_id][this.task_r[t_id].length-1][1] : 1) + "</td> \
                             <td class=\"btn\"><a>Show</a></td> \
                          </tr>"
                }
            }

            this.navigator.html(s);

            this.active = null;

            $('tr.global td.btn', this.navigator).click();

            $("#UserDetail_bg").addClass("open");
        }
    }

    private show_global() {
        this.title_label.text("Global");
        this.submission_table.html("");

        var intervals = new Array();
        var b = 0;
        var e = 0;

        for (var i = 0; i < DataStore.contest_list.length; i += 1) {
            b = DataStore.contest_list[i]["begin"];
            e = DataStore.contest_list[i]["end"];
            while (i+1 < DataStore.contest_list.length && DataStore.contest_list[i+1]["begin"] <= e) {
                i += 1;
                e = (e > DataStore.contest_list[i]["end"] ? e : DataStore.contest_list[i]["end"]);
            }
            intervals.push([b, e]);
        }

        this.draw_charts(intervals, DataStore.global_max_score,
                         this.global_s, this.global_r);
    }

    private show_contest(contest_id) {
        var contest = DataStore.contests[contest_id];

        this.title_label.text(contest["name"]);
        this.submission_table.html("");

        this.draw_charts([[contest["begin"], contest["end"]]], contest["max_score"],
                         this.contest_s[contest_id], this.contest_r[contest_id]);
    }

    private show_task(task_id) {
        var task = DataStore.tasks[task_id];
        var contest = DataStore.contests[task["contest"]];

        this.title_label.text(task["name"]);
        this.submission_table.html(this.make_submission_table(task_id));

        this.draw_charts([[contest["begin"], contest["end"]]], task["max_score"],
                         this.task_s[task_id], this.task_r[task_id]);
    }

    private draw_charts(ranges, max_score, history_s, history_r) {
        var users = DataStore.user_count;

        Chart.draw_chart(this.score_chart, // canvas object
            0, max_score, 0, 0, // y_min, y_max, x_default, h_default
            ranges, // intervals
            history_s, // data
            [102, 102, 238], // color
            [max_score*1/4, // markers
             max_score*2/4,
             max_score*3/4]);
        Chart.draw_chart(this.rank_chart, // canvas object
            users, 1, 1, users-1, // y_min, y_max, x_default, h_default
            ranges, // intervals
            history_r, // data
            [210, 50, 50], // color
            [Math.ceil (users/12), // markers
             Math.ceil (users/4 ),
             Math.floor(users/2 )]);
    }

    private make_submission_table(task_id) {
        var res = " \
<table> \
    <thead> \
        <tr> \
            <td>Time</td> \
            <td>Score</td> \
            <td>Token</td> \
            " + (DataStore.tasks[task_id]['extra_headers'].length > 0 ? "<td>" + DataStore.tasks[task_id]['extra_headers'].join("</td><td>") + "</td>" : "") + " \
        </tr> \
    </thead> \
    <tbody>";

        if (this.submissions[task_id].length == 0) {
            res += " \
        <tr> \
            <td colspan=\"" + (3 + DataStore.tasks[task_id]['extra_headers'].length) + "\">no submissions</td> \
        </tr>";
        } else {
            for (var i in this.submissions[task_id]) {
                var submission = this.submissions[task_id][i];
                const time_seconds = submission["time"] - DataStore.contests[DataStore.tasks[task_id]["contest"]]["begin"];
                const time = format_time(time_seconds, false);
                res += " \
        <tr> \
            <td>" + time + "</td> \
            <td>" + round_to_str(submission['score'], DataStore.tasks[task_id]['score_precision']) + "</td> \
            <td>" + (submission["token"] ? 'Yes' : 'No') + "</td> \
            " + (submission["extra"].length > 0 ? "<td>" + submission["extra"].join("</td><td>") + "</td>" : "") + " \
        </tr>";
            }
        }
        res += " \
    </tbody> \
</table>";
        return res;
    }

    private hide() {
        if (this.get_current_hash() != "") {
            window.history.pushState(
                {}, "", window.location.href.replace(/#.*$/, ''));
        }
        window.document.title = "Ranking";
        $("#UserDetail_bg").removeClass("open");
    }
}

export { UserDetail };
