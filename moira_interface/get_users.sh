# save users from moira list to csv file
users_file="$1_users_list.csv"
qy -s get_end_members_of_list $1 > $users_file
