'''
Post ShakeAlert Message Summary common utility functions.
'''

def get_intensity_color(mmi: int) -> str:
    """
    Get hex color code corresponding to shaking intensity (mmi).
    :param mmi: MMI param indicating shaking intensity
    :type mmi: int
    :return: A hex color code to be displayed.
    :rtype: str
    """
    if not isinstance(mmi, int):
        mmi = int(mmi)  # attempt int cast if needed
    if mmi < 2:
        return "#000000"  # white
    if mmi == 2:
        return "#c8d0fd"
    if mmi == 3:
        return "#b3f3fe"
    if mmi == 4:
        return "#b0fff7"
    if mmi == 5:
        return "#afff93"
    if mmi == 6:
        return "#fefb3c"
    if mmi == 7:
        return "#f0c52f"
    if mmi == 8:
        return "#e58620"
    if mmi == 9:
        return "#da0201"
    if mmi == 10:
        return "#ab0101"
    if mmi > 10:
        return "#800000"  # maroon
    return "#ffffff"  # black