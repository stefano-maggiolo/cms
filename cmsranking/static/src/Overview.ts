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
import * as Raphael from "raphael";

import { DataStore } from "./DataStore";
import { Scoreboard } from "./Scoreboard";

class Overview {
    private static instance: Overview;

    private static readonly PAD_T = 20;
    private static readonly PAD_B = 10;
    private static readonly PAD_L = 10;
    private static readonly PAD_R = 10;

    private static readonly SCORE_STEPS = 15;

    private static readonly MARKER_PADDING = 2;
    private static readonly MARKER_RADIUS = 2.5;
    private static readonly MARKER_LABEL_WIDTH = 50;
    private static readonly MARKER_LABEL_HEIGHT = 20;
    private static readonly MARKER_ARROW_WIDTH = 20;
    private static readonly MARKER_STROKE_WIDTH = 2;

    // scores[0] contains the number of users with a score of zero
    // scores[i] (with i in [1..SCORE_STEPS]) contains the number of users with
    //     a score in the half-open interval [i * (max_score / SCORE_STEPS),
    //     (i+1) * (max_score / SCORE_STEPS)). for i == 0 the interval is open
    // scores[SCORE_STEPS+1] contins the number of user with the max_score
    // see also get_score_class()
    private scores: number[];

    private width: number;
    private height: number;
    private paper;
    private score_axis;
    private rank_axis;
    private score_line;
    private score_back;

    // Selected users in the overview. In particular we sort using these keys:
    // - the global score
    // - the last name
    // - the first name
    // - the key
    private user_list: any[];

    public static getInstance() {
      if (!Overview.instance) {
        Overview.instance = new Overview();
      }
      return Overview.instance;
    }

    private constructor() {
        var $elem = $("#Overview");

        this.width = $elem.width();
        this.height = $elem.height();

        this.paper = Raphael($elem[0], this.width, this.height);

        this.scores = [];
        for (var i = 0; i <= Overview.SCORE_STEPS + 1; i += 1) {
            this.scores.push(0);
        }

        this.create_score_chart();

        this.update_score_axis();
        this.update_rank_axis();


        $(window).resize(() => {
            this.width = $elem.width();
            this.height = $elem.height();

            this.paper.setSize(this.width, this.height);

            this.update_score_chart(0);

            this.update_score_axis();
            this.update_rank_axis();

            this.update_markers(0);
        });


        DataStore.user_update.add((key, old_data, data) => {
            if (old_data["markers"]) {
                data["markers"] = old_data["markers"];
                delete old_data["markers"];
            }
            if (old_data["marker_c_anim"]) {
                data["marker_c_anim"] = old_data["marker_c_anim"];
                delete old_data["marker_c_anim"];
            }
            if (old_data["marker_u_anim"]) {
                data["marker_u_anim"] = old_data["marker_u_anim"];
                delete old_data["marker_u_anim"];
            }
            if ($.inArray(old_data, this.user_list) != -1) {
                this.user_list.splice($.inArray(old_data, this.user_list), 1, data);
            }
        });

        DataStore.score_events.add(this.score_handler.bind(this));
        DataStore.rank_events.add(this.rank_handler.bind(this));
        DataStore.select_events.add(this.select_handler.bind(this));


        // HEADERS ("Score" and "Rank")
        this.paper.setStart();
        this.paper.text(4, 10, "Score").attr("text-anchor", "start");
        this.paper.text(this.width - 4, 10, "Rank").attr("text-anchor", "end");
        var set = this.paper.setFinish();
        set.attr({"font-size": "12px", "fill": "#000000", "stroke": "none", "font-family": "sans-serif", "opacity": 0});

        $elem.mouseenter(() => {
            set.animate({"opacity": 1}, 1000);
        });

        $elem.mouseleave(() => {
            set.animate({"opacity": 0}, 1000);
        });

        // Load initial data.
        this.user_list = [];
        $.each(DataStore.users, (u_id, user) => {
            if (user["selected"] > 0)
            {
                this.user_list.push(user);
            }
        });
        this.user_list.sort(Overview.compare_users);
        this.update_markers(0);
    }


    /** SCORE & RANK AXIS */

    private update_score_axis() {
        var d = Raphael.format(
          "M {1},{3} L {1},{7} M {0},{4} L {2},{4} M {0},{5} L {2},{5} M {0},{6} L {2},{6}",
          Overview.PAD_L - 4,
          Overview.PAD_L,
          Overview.PAD_L + 4,
          Overview.PAD_T,
          Overview.PAD_T + (this.height - Overview.PAD_T - Overview.PAD_B) * 0.25,
          Overview.PAD_T + (this.height - Overview.PAD_T - Overview.PAD_B) * 0.50,
          Overview.PAD_T + (this.height - Overview.PAD_T - Overview.PAD_B) * 0.75,
          this.height - Overview.PAD_B);

        if (this.score_axis) {
            this.score_axis.attr("path", d);
        } else {
            this.score_axis = this.paper.path(d).attr(
                {"fill": "none", "stroke": "#b8b8b8", "stroke-width": 3, "stroke-linecap": "round"});
        }
    }


    private update_rank_axis() {
        var d = Raphael.format(
          "M {1},{3} L {1},{4} M {0},{3} L {2},{3} M {0},{4} L {2},{4}",
          this.width - Overview.PAD_R - 4,
          this.width - Overview.PAD_R,
          this.width - Overview.PAD_R + 4,
          Overview.PAD_T,
          this.height - Overview.PAD_B);

        var ranks = [
            { color: "#ffd700", ratio: 1/12 },
            { color: "#c0c0c0", ratio: 2/12 },
            { color: "#cd7f32", ratio: 3/12 },
            { color: "#000000", ratio: 6/12 }
        ];
        const stops = [];
        var base = 0;
        for (var i = 0; i < ranks.length; i++) {
            stops.push(ranks[i].color + ":" + (base + (ranks[i].ratio / 3)) * 100);
            stops.push(ranks[i].color + ":" + (base + (ranks[i].ratio / 3 * 2)) * 100);
            base += ranks[i].ratio;
        }
        const stops_str = stops.join("-");

        if (this.rank_axis) {
            this.rank_axis.attr("path", d);
        } else {
            // Since raphael does not support gradients for stroke, we set the fill attr to it,
            // then move the value to stroke.
            this.rank_axis = this.paper.path(d).attr({
                "fill": "270-" + stops_str,
                "stroke-width": 3,
                "stroke-linecap": "round"
            });
            this.rank_axis.node.setAttribute("stroke", this.rank_axis.node.getAttribute("fill"));
            this.rank_axis.node.setAttribute("fill", "none");
        }
    }


    /** SCORE CHART */


    private make_path_for_score_chart() {
        // For each element of this.scores, we convert the number it contains
        // to a distance from the score axis and then create a smooth path that
        // passes on all those points.
        // To convert the number of users to a distance we use the following
        // formula (a parabola, open down):  d(x) = a * x^2 + b * x + c
        // with a, b and c parameters chosen such that:
        // - d(0) = 0;        - d'(0) = 3/2;
        // - d(max_users) = 3/4 * width (excluding padding);

        var max_users = DataStore.user_count;
        var a = (3/4 * (this.width - Overview.PAD_R - Overview.PAD_L) - 3/2 * max_users) / (max_users * max_users);
        var b = 3/2;
        var c = 0;

        var s_path = "";
        for (var i = 0; i <= Overview.SCORE_STEPS + 1; i += 1) {
            var x = Overview.PAD_L + a * this.scores[i] * this.scores[i] + b * this.scores[i] + c;
            var y = this.height - Overview.PAD_B - i * (this.height - Overview.PAD_T - Overview.PAD_B) / (Overview.SCORE_STEPS + 1);
            if (i == 0) {
                s_path += Raphael.format("M {0},{1} R", x, y);
            } else {
                s_path += Raphael.format(" {0},{1}", x, y);
            }
        }

        return s_path;
    }


    private recompute() {
        // Recompute this.scores
        for (var i = 0; i <= Overview.SCORE_STEPS + 1; i += 1) {
            this.scores[i] = 0;
        }

        var users = DataStore.users;
        var max_score = DataStore.global_max_score;

        for (var u_id in users) {
            this.scores[this.get_score_class(users[u_id]["global"], max_score)] += 1;
        }
    }


    private create_score_chart() {
        this.recompute();
        var s_path = this.make_path_for_score_chart();
        this.score_line = this.paper.path(s_path).attr({"fill": "none", "stroke": "#cccccc", "stroke-width": 2, "stroke-linecap": "round"});
        s_path += Raphael.format(" L {0},{1} {0},{2} Z", Overview.PAD_L, Overview.PAD_T, this.height - Overview.PAD_B);
        this.score_back = this.paper.path(s_path).attr({"fill": "0-#E4E4E4-#DADADB", "stroke": "none"});
        this.score_back.toBack();
    }


    private update_score_chart(t) {
        var s_path = this.make_path_for_score_chart();
        this.score_line.animate({'path': s_path}, t);
        s_path += Raphael.format(" L {0},{1} {0},{2} Z",
            Overview.PAD_L,
            Overview.PAD_T,
            this.height - Overview.PAD_B);
        this.score_back.animate({'path': s_path}, t);
    }


    private get_score_class(score, max_score) {
        if (score <= 0) {
            return 0;
        } else if (score >= max_score) {
            return Overview.SCORE_STEPS + 1;
        } else {
            return Math.floor(score / max_score * Overview.SCORE_STEPS) + 1;
        }
    }


    /** MARKERS */


    // We keep a sorted list of user that represent the current order of the
    // Compare two users. Returns -1 if "a < b" or +1 if "a >= b"
    // (where a < b means that a shoud go above b in the overview)
    private static compare_users(a, b) {
        if ((a["global"] > b["global"]) || ((a["global"] == b["global"]) &&
           ((a["l_name"] < b["l_name"]) || ((a["l_name"] == b["l_name"]) &&
           ((a["f_name"] < b["f_name"]) || ((a["f_name"] == b["f_name"]) &&
           (a["key"] <= b["key"]))))))) {
            return -1;
        } else {
            return +1;
        }
    }


    private make_path_for_marker(s_h, u_h, r_h) {
        // The path is composed of a label (whose vertical center is at u_h,
        // Overview.MARKER_LABEL_WIDTH wide and Overview.MARKER_LABEL_HEIGHT high),
        // made of two horizontal (H) lines (for top and bottom), delimited on
        // the right by two straight lines (L) forming an arrow (which is
        // Overview.MARKER_ARROW_WIDTH wide), with its center at an height of r_h.
        // On the left two cubic bezier curves (C) start tangentially from the
        // label and end, still tangentially, on an elliptic arc (A), with its
        // center at an height of s_h and a radius of Overview.MARKER_RADIUS.
        // The path starts just above the arc, with the first cubic bezier.

        // TODO Most of these values are constants, no need to recompute
        // everything again every time.

        return Raphael.format(
            "M {0},{5} C {1},{5} {1},{6} {2},{6} H {3} L {4},{7} {3},{8} H {2} C {1},{8} {1},{9} {0},{9} A {10},{10} 0 0,1 {0},{5} Z",
            Overview.PAD_L,
            (Overview.PAD_L + this.width - Overview.PAD_R - Overview.MARKER_ARROW_WIDTH - Overview.MARKER_LABEL_WIDTH) / 2,
            this.width - Overview.PAD_R - Overview.MARKER_ARROW_WIDTH - Overview.MARKER_LABEL_WIDTH,
            this.width - Overview.PAD_R - Overview.MARKER_ARROW_WIDTH,
            this.width - Overview.PAD_R,
            s_h - Overview.MARKER_RADIUS,
            u_h - (Overview.MARKER_LABEL_HEIGHT - Overview.MARKER_STROKE_WIDTH) / 2,
            r_h,
            u_h + (Overview.MARKER_LABEL_HEIGHT - Overview.MARKER_STROKE_WIDTH) / 2,
            s_h + Overview.MARKER_RADIUS,
            Overview.MARKER_RADIUS);
    }


    private create_marker(user, s_h, u_h, r_h, t) {
        var d = this.make_path_for_marker(s_h, u_h, r_h);

        // Map the color_index given by DataStore to the actual color
        // (FIXME This almost duplicates some code in Ranking.css...)
        switch (user["selected"]) {
            case 1:  // Blue
                var color_a = "#729fcf";
                var color_b = "#3465a4";
                break;
            case 2:  // Butter
                var color_a = "#fce94f";
                var color_b = "#edd400";
                break;
            case 3:  // Red
                var color_a = "#ef2929";
                var color_b = "#cc0000";
                break;
            case 4:  // Chameleon
                var color_a = "#8ae234";
                var color_b = "#73d216";
                break;
            case 5:  // Orange
                var color_a = "#fcaf3e";
                var color_b = "#f57900";
                break;
            case 6:  // Plum
                var color_a = "#ad7fa8";
                var color_b = "#75507b";
                break;
            case 7:  // Aluminium
                var color_a = "#babdb6";
                var color_b = "#888a85";
                break;
            case 8:  // Chocolate
                var color_a = "#e9b96e";
                var color_b = "#c17d11";
                break;
        }

        this.paper.setStart();
        this.paper.path(d).attr({
            "fill": color_b,
            "stroke": color_a,
            "stroke-width": Overview.MARKER_STROKE_WIDTH,
            "stroke-linejoin": "round"});
        // Place the text inside the label, with a padding-right equal to its
        // padding-top and padding-bottom.
        var t_x = this.width - Overview.PAD_R - Overview.MARKER_ARROW_WIDTH - (Overview.MARKER_LABEL_HEIGHT - 12) / 2;
        this.paper.text(t_x, u_h, this.transform_key(user)).attr({
            "fill": "#ffffff",
            "stroke": "none",
            "font-family": "sans-serif",
            "font-size": "12px",
            "text-anchor": "end"});
        var set = this.paper.setFinish();
        set.attr({"cursor": "pointer",
                  "opacity": 0});

        set.click(function () {
            Scoreboard.scroll_into_view(user["key"]);
        });

        user["markers"] = set;

        user["marker_c_anim"] = Raphael.animation({"opacity": 1}, t, function () {
            delete user["marker_c_anim"];
        });
        set.animate(user["marker_c_anim"]);
    }

    private transform_key(user) {
      var s = user['f_name'] + ' ' + user['l_name'];
      var sl = s.split(' ');
      var out = '';
      for (var i = 0; i < sl.length; i++) {
          if (sl[i].length > 0) {
              out += sl[i][0];
          }
      }
      if (user["team"] != null && user["team"] != undefined) {
          return user['team'] + '-' + out;
      } else {
          return out;
      }
    }


    private update_marker(user, s_h, u_h, r_h, t) {
        var d = this.make_path_for_marker(s_h, u_h, r_h);

        // If the duration of the animation is 0 or if the element has just
        // been created (i.e. its creation animation hasn't finished yet) then
        // just set the new path and position. Else, animate them.
        if (t && !user["marker_c_anim"]) {
            user["markers"].stop();
            user["marker_u_anim"] = Raphael.animation({"path": d, "y": u_h}, t, function () {
                delete user["marker_u_anim"];
            });
            user["markers"].animate(user["marker_u_anim"]);
        } else {
            user["markers"].attr({"path": d, "y": u_h});
        }
    }


    private delete_marker(user, t) {
        var markers = user["markers"];
        delete user["markers"];

        // If an update animation is running, we stop and delete it
        if (user["marker_u_anim"]) {
            markers.stop();
            delete user["marker_u_anim"];
        }

        var anim = Raphael.animation({"opacity": 0}, t, function () {
            markers.remove();
        });
        markers.animate(anim);

        this.user_list.splice($.inArray(user, this.user_list), 1);
        this.update_markers(t);
    };


    private get_score_height(score, max_score) {
        if (max_score <= 0) {
            return this.height - Overview.PAD_B;
        }
        return this.height - Overview.PAD_B - score / max_score * (this.height - Overview.PAD_T - Overview.PAD_B);
    }


    private get_rank_height(rank, max_rank) {
        if (max_rank <= 1) {
            return Overview.PAD_T;
        }
        return Overview.PAD_T + (rank - 1) / (max_rank - 1) * (this.height - Overview.PAD_T - Overview.PAD_B);
    }


    private merge_clusters(a, b) {
        // See the next function to understand the purpose of this function
        var middle = (a.n * (a.b + a.e) / 2 + b.n * (b.b + b.e) / 2) / (a.n + b.n);
        a.list = a.list.concat(b.list);
        a.n += b.n;
        a.b = middle - (a.n * Overview.MARKER_LABEL_HEIGHT + (a.n - 1) * Overview.MARKER_PADDING) / 2;
        a.e = a.b + a.n * Overview.MARKER_LABEL_HEIGHT + (a.n - 1) * Overview.MARKER_PADDING;
    }


    private update_markers(t) {
        // Use them as shortcut
        var h = Overview.MARKER_LABEL_HEIGHT;
        var p = Overview.MARKER_PADDING;

        // We iterate over all selected users (in top-to-bottom order). For
        // each of them we create a cluster which, initally, contains just that
        // user. Then, if the cluster overlaps with another, we merge them and
        // increase its size so that its element don't overlap anymore. We
        // repeat this process unit no two clusters overlap, and then proceed
        // to the next user. We also take care that no cluster is outside the
        // visible area, either above or below.

        // The list of clusters and its size (n == cs.length)
        var cs = new Array();
        var n = 0;

        for (var i in this.user_list) {
            var user = this.user_list[i];
            var r_height = this.get_rank_height(user["rank"], DataStore.user_count);

            // 'b' (for begin) is the y coordinate of the top of the cluster
            // 'e' (for end) is the y coordinate of the bottom of the cluster
            // 'n' is the number of items it contains (c.n == c.list.length)
            cs.push({'b': r_height - h/2, 'e': r_height + h/2, 'list': [user], 'n': 1});
            n += 1;

            // Check if it overlaps with the one above it
            while (n > 1 && cs[n-2].e + p > cs[n-1].b) {
                this.merge_clusters(cs[n-2], cs[n-1]);
                cs.pop();
                n -= 1;
            }

            // Check if it overflows at the top of the visible area
            if (cs[n-1].b < Overview.PAD_T - h/2) {
                cs[n-1].e += (Overview.PAD_T - h/2) - cs[n-1].b;
                cs[n-1].b = Overview.PAD_T - h/2;
            }
        }

        // Check if it overflows at the bottom of the visible area
        while (n > 0 && cs[n-1].e > this.height - Overview.PAD_B + h/2) {
            cs[n-1].b += (this.height - Overview.PAD_B + h/2) - cs[n-1].e;
            cs[n-1].e = this.height - Overview.PAD_B + h/2;

            // Check if it overlaps with the one above it
            if (n > 1 && cs[n-2].e + p > cs[n-1].b) {
                this.merge_clusters(cs[n-2], cs[n-1]);
                cs.pop();
                n -= 1;
            }
        }

        // If it overflows again at the top then there's simply not enough
        // space to hold them all. Compress them.
        if (n > 0 && cs[0].b < Overview.PAD_T - h/2) {
            cs[0].b = Overview.PAD_T - h/2;
        }

        // Proceed with the actual drawing
        for (var i in cs) {
            var c = cs[i];
            var begin = c.b;
            var step = (c.e - begin - h) / (c.n - 1);  // NaN if c.n == 1

            for (var j in c.list) {
                var user = c.list[j];

                var s_height = this.get_score_height(user["global"], DataStore.global_max_score);
                var r_height = this.get_rank_height(user["rank"], DataStore.user_count);

                if (user["markers"]) {
                    // Update the existing marker
                    this.update_marker(user, s_height, begin + h/2, r_height, t);
                } else {
                    // Create a new marker
                    this.create_marker(user, s_height, begin + h/2, r_height, t);
                }

                begin += step;  // begin is NaN if step is NaN: no problem
                                // because if c.n == 1 begin won't be used again
            }
        }
    }


    private score_handler(u_id, user, t_id, task, delta) {
        var new_score = user["global"];
        var old_score = new_score - delta;
        var max_score = DataStore.global_max_score;

        this.scores[this.get_score_class(old_score, max_score)] -= 1;
        this.scores[this.get_score_class(new_score, max_score)] += 1;

        this.update_score_chart(1000);

        if (user["selected"] > 0) {
            this.user_list.sort(Overview.compare_users);
            this.update_markers(1000);
        }
    }


    private rank_handler(u_id, user, delta) {
        if (user["selected"] > 0) {
            this.update_markers(1000);
        }
    }


    private select_handler(u_id, color) {
        var user = DataStore.users[u_id];
        if (color > 0) {
            this.user_list.push(user);
            this.user_list.sort(Overview.compare_users);
            this.update_markers(1000);
        } else {
            this.delete_marker(DataStore.users[u_id], 1000);
        }
    }

    /* TODO: When users get added/removed the total user count changes and all
       rank "markers" need to be adjusted!
     */
}

export { Overview };
