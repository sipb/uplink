class Class:
    mailing_list: str | None
    name: str
    academic_year: str
    term: str
    role: str
    
    _role_names = {
        'st': 'Student',
        'te': 'Teacher',
        'ob': 'Observer',
        'ta': 'TA',
    }

    _terms = {
        'ja': 'IAP',
        'sp': 'Spring',
        'fa': 'Fall',
        'su': 'Summer',
    }


    def __init__(self, mailing_list=None, name=None, academic_year=None, term=None, role=None):
        self.mailing_list = mailing_list
        if mailing_list:
            name = mailing_list

            self.mailing_list = name

            # Examples of names
            # * canvas-2023ja_11.s188-st
            # * canvas-2023sp_9.00-st
            # * canvas-2023q5_pe_0202.3-st
            # * canvas-2021su_sp.100_cwi-susan-st (note 3 hyphens instead of 2)
            app, name = name.split('-', maxsplit=1)
            assert app == 'canvas'
            
            # Get class role (teacher, student, etc)
            parts = name.rsplit('-', maxsplit=1)
            role = parts[1]
            if role in Class._role_names:
                self.role = Class._role_names[role]
            else:
                self.role = f'Other ({role})'
            
            # Get class term and academic year
            date, name = parts[0].split('_', maxsplit=1)
            year = date[:4]
            self.academic_year = f'{int(year)-1}-{year[2:4]}'
            term = date[4:]
            if term in Class._terms:
                self.term = Class._terms[term]
            else:
                # For Q1, Q2, etc
                self.term = term.upper()
            self.name = name.upper()
        else:
            self.name = name
            self.academic_year = academic_year
            self.term = term
            self.role = role

    def __str__(self):
        return f'{self.name} {self.role} ({self.term} {self.academic_year})'

    def __repr__(self):
        if self.mailing_list:
            return f'Class("{self.mailing_list}")'
        else:
            return f'Class(name={self.name}, academic_year={self.academic_year}, term={self.term}, role={self.role})'

    def get_room_alias(self):
        """
        Programatically generate a channel name for the given class
        This is customizable, for now just the mailing list name
        """
        # Note that Matrix allows more than one room alias
        # For now, one should be enough
        assert self.mailing_list is not None
        return self.mailing_list

    @staticmethod
    def get_list_from_mailing_lists(lists: list[str]):
        return [Class(l) for l in lists if l.startswith('canvas-')]