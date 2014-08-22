/* This script enables client-side paging of long tables.
** All tables with the .viewTable class are 
**    (1) hidden by default
**    (2) indexed/paginated using jquery.dataTables.min.js
**    (3) made visible (after page has been completely loaded and pagination is done)
*/

$(document).ready( function() {
    
    // determine type of content table used on this page
    if ($('table.viewTable.terms').length > 0) {
        // table of terms (5 logical <tr> for 1 visible table row
        $('table.viewTable.terms').DataTable({
            ordering: false,
            searching: false,
            "lengthMenu": [ [50, 125, 250, -1], [10, 25, 50, "All"] ] //note: every table row (visible) corresponds to five table rows (logical)
        });
    } else {
        // all other tables
        $('table.viewTable').DataTable({
            ordering: false,
            searching: false,
            "lengthMenu": [ [10, 25, 50, -1], [10, 25, 50, "All"] ]
            });
    }
    
    /* show table only after page has been loaded completely */
    $('table.viewTable').show();

})
