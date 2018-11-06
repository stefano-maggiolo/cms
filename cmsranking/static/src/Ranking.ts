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

require("../style/Ranking");

// To include them in the bundle since they are only linked from Python.
require("../img/logo.png");
require("../img/face.png");
require("../img/flag.png");

import * as $ from "jquery";

import { DataStore } from "./DataStore";
import { HistoryStore } from "./HistoryStore";
import { Overview } from "./Overview";
import { Scoreboard } from "./Scoreboard";
import { TeamSearch } from "./TeamSearch";
import { TimeView } from "./TimeView";
import { UserDetail } from "./UserDetail";

$(document).ready(function() {
    DataStore.init(function(){
        HistoryStore.getInstance();
        UserDetail.init();
        TimeView.init();
        TeamSearch.init();
        Overview.getInstance();
        Scoreboard.init();
    });
});
