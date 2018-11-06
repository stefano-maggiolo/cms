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

class Config {
    public static get_contest_list_url() {
        return "contests/";
    }

    public static get_contest_read_url(c_key) {
        return "contests/" + c_key;
    }

    public static get_task_list_url() {
        return "tasks/";
    }

    public static get_task_read_url(t_key) {
        return "tasks/" + t_key;
    }

    public static get_team_list_url() {
        return "teams/";
    }

    public static get_team_read_url(t_key) {
        return "teams/" + t_key;
    }

    public static get_user_list_url() {
        return "users/";
    }

    public static get_user_read_url(u_key) {
        return "users/" + u_key;
    }

    public static get_flag_url(t_key) {
        return "flags/" + t_key;
    }

    public static get_face_url(u_key) {
        return "faces/" + u_key;
    }

    public static get_submissions_url(u_key) {
        return "sublist/" + u_key;
    }

    public static get_score_url() {
        return "scores";
    }

    public static get_event_url(last_event_id) {
        return "events?last_event_id=" + last_event_id;
    }

    public static get_history_url() {
        return "history";
    }
}

export { Config };
